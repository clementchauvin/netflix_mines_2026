from fastapi import FastAPI, HTTPException  # Ajout de HTTPException
from pydantic import BaseModel
from db import get_connection
import sqlite3
import jwt
import datetime

app = FastAPI()

@app.get("/ping")
def ping():
    return {"message": "pong"}

class Film(BaseModel):
    id: int | None = None
    nom: str
    note: float | None = None
    dateSortie: int
    image: str | None = None
    video: str | None = None
    genreId: int | None = None

@app.post("/films")
async def createFilm(film: Film):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Film (Nom, Note, DateSortie, Image, Video, Genre_ID)  
            VALUES (?, ?, ?, ?, ?, ?) RETURNING *
            """, (film.nom, film.note, film.dateSortie, film.image, film.video, film.genreId))
        
        res = cursor.fetchone()
        return dict(res) 

# les GET de films
@app.get("/films/{id}")
def get_one_film(id: int):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM Film WHERE ID = ?", (id,))   
        res = cursor.fetchone()
        
        if res is None:
            raise HTTPException(status_code=404, detail="Film not found")
            
        return dict(res)


@app.get("/films")
def get_films(page: int = 1, per_page: int = 20, genre_id: int | None = None):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        offset = (page - 1) * per_page
        
        count_query = "SELECT COUNT(*) FROM Film"
        count_params = []
        if genre_id is not None:
            count_query += " WHERE Genre_ID = ?"
            count_params.append(genre_id)
            
        cursor.execute(count_query, count_params)
        total_films = cursor.fetchone()[0]

        query = "SELECT * FROM Film"
        params = []
        
        if genre_id is not None:
            query += " WHERE Genre_ID = ?"
            params.append(genre_id)
            
        query += " ORDER BY DateSortie DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        cursor.execute(query, params)   
        res = cursor.fetchall()
        
        return {
            "data": [dict(row) for row in res],
            "page": page,
            "per_page": per_page,
            "total": total_films
        }

#Catégories de films (genre,...)
@app.get("/genres")
def list_genres():
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = "SELECT * FROM Genre ORDER BY Type ASC"
        cursor.execute(query)
        res = cursor.fetchall()
        return [dict(row) for row in res]
            
SECRET_KEY = "super_mot_de_passe_secret_netflix"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 120 

def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
  
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt



def get_current_user_id(authorization):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="token pas bon")
    
    token = authorization.split(" ")[1]
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        
        if user_id is None:
            raise HTTPException(status_code=401, detail="token pas bon")
            
        return user_id
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token pas bon")
    

class UserAuth(BaseModel):
    email: str
    password: str
    pseudo: str | None = None

class PreferenceIn(BaseModel):
    genre_id: int




@app.post("/auth/register")
def register(user: UserAuth):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT ID FROM Utilisateur WHERE AdresseMail = '{user.email}'")
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="email dejaa utilisé")
            
        
        cursor.execute(f"""
            INSERT INTO Utilisateur (AdresseMail, Pseudo, MotDePasse) 
            VALUES ('{user.email}', '{user.pseudo}', '{user.password}') 
            RETURNING ID
        """)
        new_user_id = cursor.fetchone()["ID"]
        conn.commit()
        access_token = create_access_token(data={"user_id": new_user_id})
        return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/login")
def login(user: UserAuth):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT ID FROM Utilisateur WHERE AdresseMail = '{user.email}' AND MotDePasse = '{user.password}'")
        database_user = cursor.fetchone()
        
        if not database_user:
            raise HTTPException(status_code=401, detail="Identifiants pas bon")
            
        access_token = create_access_token(data={"user_id": database_user["ID"]})
        return {"access_token": access_token, "token_type": "bearer"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
