from flask import Flask, render_template, request
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import json

app = Flask(__name__)

# Tu API Key de TMDb
API_KEY = '452bf7614eb701e35cb81bcd24b116a6'

# IDs de géneros en TMDb
GENRES = {
    'Acción': '28',
    'Aventura': '12',
    'Terror': '27'
}

app.secret_key = '123456789'  # Cambia esta clave por algo seguro


# Configuración de SQLite
DATABASE = 'data/testimonials.db'

def init_db():
    """
    Crea las tablas necesarias si no existen.
    """
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        # Tabla de usuarios
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )''')
        # Tabla de testimonios
        cursor.execute('''CREATE TABLE IF NOT EXISTS testimonials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            testimonial TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )''')
        conn.commit()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_password))
                conn.commit()
                flash('Usuario registrado exitosamente. ¡Inicia sesión!')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('El nombre de usuario ya existe. Prueba con otro.')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, password FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['username'] = username
                flash('Inicio de sesión exitoso.')
                return redirect(url_for('testimonios'))
            else:
                flash('Usuario o contraseña incorrectos.')
    return render_template('login.html')

@app.route('/testimonios', methods=['GET', 'POST'])
def testimonios():
    if 'user_id' not in session:
        flash('Debes iniciar sesión para acceder a esta página.')
        return redirect(url_for('login'))

    if request.method == 'POST':
        testimonial = request.form['testimonial']
        user_id = session['user_id']

        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO testimonials (user_id, testimonial) VALUES (?, ?)', (user_id, testimonial))
            conn.commit()
            flash('¡Tu testimonio ha sido enviado!')

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT t.testimonial, u.username FROM testimonials t JOIN users u ON t.user_id = u.id')
        testimonies = cursor.fetchall()

    return render_template('testimonios.html', testimonies=testimonies)

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión.')
    return redirect(url_for('login'))


# Función para obtener los últimos estrenos desde la API
def fetch_new_releases():
    """
    Consulta la API de TMDb para obtener las películas actualmente en cartelera.
    """
    url = f'https://api.themoviedb.org/3/movie/now_playing?api_key={API_KEY}&language=es-ES&page=1'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('results', [])  # Devuelve los resultados o una lista vacía
    return []

# Función para obtener películas por género
def get_movies_by_genre(genre_id):
    """
    Consulta la API de TMDb para obtener películas populares de un género específico.
    """
    url = f'https://api.themoviedb.org/3/discover/movie?api_key={API_KEY}&with_genres={genre_id}&sort_by=popularity.desc'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data.get('results', [])  # Retorna las películas o una lista vacía si no hay resultados
    return []

@app.route('/')
def welcome():
    """
    Página de bienvenida que se muestra al inicio.
    """
    return render_template('welcome.html')

@app.route('/movies')
def home():
    """
    Página principal con un formulario para seleccionar un género.
    """
    return render_template('index.html', genres=GENRES)

@app.route('/recommend', methods=['POST'])
def recommend():
    """
    Procesa el formulario enviado, consulta las películas y las muestra en la página de recomendaciones.
    """
    genre = request.form['genre']  # Obtiene el género seleccionado del formulario
    genre_id = GENRES.get(genre)  # Obtiene el ID del género
    if not genre_id:
        return render_template('error.html', message="Género no encontrado.")  # Muestra un error si el género no es válido

    # Obtiene las películas desde la API de TMDb
    movies = get_movies_by_genre(genre_id)

    # Limitar el número de películas para mostrar (ejemplo: las 10 primeras)
    movies = movies[:10]

    return render_template('recommendations.html', movies=movies, genre=genre)

@app.route('/estrenos')
def estrenos():
    """
    Página que muestra los nuevos estrenos.
    """
    new_releases = fetch_new_releases()  # Ahora se usan los datos dinámicamente desde la API
    return render_template('estreno.html', new_releases=new_releases)

@app.route('/trailer/<movie_id>')
def get_trailer(movie_id):
    """
    Obtiene la URL del tráiler desde la API de TMDb.
    """
    url = f'https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={API_KEY}'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        for video in data.get('results', []):
            if video['type'] == 'Trailer' and video['site'] == 'YouTube':
                return {'trailer_url': f"https://www.youtube.com/embed/{video['key']}"}
    return {'trailer_url': None}

@app.route('/populares')
def populares():
    """
    Página que muestra películas populares agrupadas por género.
    """
    popular_movies = {}
    
    for genre, genre_id in GENRES.items():
        # Obtener películas populares para cada género
        movies = get_movies_by_genre(genre_id)[:5]  # Limita a las 5 películas más populares por género
        popular_movies[genre] = movies

    return render_template('populares.html', popular_movies=popular_movies)

def fetch_faq():
    """
    Carga las preguntas frecuentes desde un archivo JSON.
    Si hay un error, devuelve una lista vacía o un mensaje predeterminado.
    """
    json_path = os.path.join(os.getcwd(), 'data', 'faq.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            faqs = json.load(f)
            return faqs
    except FileNotFoundError:
        print("Archivo FAQ no encontrado.")
        return []  # Devuelve una lista vacía si el archivo no existe
    except json.JSONDecodeError:
        print("Error al decodificar el archivo JSON.")
        return []  # Devuelve una lista vacía si hay un error de formato

@app.route('/faq')
def faq():
    """
    Página que muestra las preguntas frecuentes.
    """
    faqs = fetch_faq()
    return render_template('faq.html', faqs=faqs)


if __name__ == '__main__':
    app.run(debug=True)
