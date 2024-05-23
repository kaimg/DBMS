from flask import Flask, render_template, request, redirect, session, g, url_for, flash
from db import get_db, close_db
from admin_routes import admin_bp
from user_routes import user_bp

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key

app.register_blueprint(admin_bp)
app.register_blueprint(user_bp)

@app.teardown_appcontext
def teardown_db(exception):
    close_db()

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/home')
def home():
    if 'user_id' in session:
        if session.get('is_admin'):
            return redirect(url_for('admin'))
        else:
            return redirect(url_for('user'))
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = get_db()
        cur = db.cursor()
        username = request.form['username']
        password = request.form['password']
        cur.execute(
            'SELECT user_id, username, password, is_admin FROM users WHERE username = %s',
            (username, ))
        user = cur.fetchone()
        cur.close()
        if user and user[2] == password:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['is_admin'] = user[3]
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            db = get_db()
            cur = db.cursor()
            username = request.form['username']
            password = request.form['password']
            email = request.form['email']

            # Check if the username already exists
            cur.execute('SELECT * FROM users WHERE username = %s', (username,))
            existing_user = cur.fetchone()
            if existing_user:
                flash('Username already taken', 'error')
                return redirect(url_for('register'))

            # Check if the email already exists
            cur.execute('SELECT * FROM users WHERE email = %s', (email,))
            existing_email = cur.fetchone()
            if existing_email:
                flash('Email already registered', 'error')
                return redirect(url_for('register'))

            cur.execute(
                'INSERT INTO users (username, password, email, is_admin) VALUES (%s, %s, %s, %s)',
                (username, password, email, False))
            db.commit()
            cur.close()
            flash('Registration successful', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.rollback()
            print("Error: ", str(e))
            flash('Registration failed', 'error')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('landing'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    results = []
    query = ""
    if request.method == 'POST':
        query = request.form['query']
        db = get_db()
        cur = db.cursor()

        # Search in teams
        cur.execute("SELECT team_id, name, 'team' AS source FROM teams WHERE name ILIKE %s", ('%' + query + '%',))
        results.extend(cur.fetchall())

        # Search in coaches
        cur.execute("SELECT coach_id, name, 'coach' AS source FROM coaches WHERE name ILIKE %s", ('%' + query + '%',))
        results.extend(cur.fetchall())

        # Search in players
        cur.execute("SELECT player_id, name, 'player' AS source FROM players WHERE name ILIKE %s", ('%' + query + '%',))
        results.extend(cur.fetchall())

        # Search in stadiums
        cur.execute("SELECT stadium_id, name, 'stadium' AS source FROM stadiums WHERE name ILIKE %s", ('%' + query + '%',))
        results.extend(cur.fetchall())

        # Search in leagues
        cur.execute("SELECT league_id, name, 'league' AS source FROM leagues WHERE name ILIKE %s", ('%' + query + '%',))
        results.extend(cur.fetchall())

        cur.close()

    return render_template('search.html', results=results, query=query)
@app.route('/team/<int:team_id>')
def team_profile(team_id):
    db = get_db()
    cur = db.cursor()

    # Get team details along with stadium and coach
    cur.execute("""
        SELECT t.name, t.founded_year, s.name AS stadium_name, c.name AS coach_name 
        FROM teams t 
        JOIN stadiums s ON t.stadium_id = s.stadium_id 
        JOIN coaches c ON t.coach_id = c.coach_id 
        WHERE t.team_id = %s
    """, (team_id,))
    team = cur.fetchone()

    # Get players
    cur.execute("""
        SELECT p.player_id, p.name, p.age, p.position 
        FROM players p 
        WHERE p.team_id = %s
    """, (team_id,))
    players = cur.fetchall()

    # Get scores
    cur.execute("""
        SELECT m.date, s.score 
        FROM scores s 
        JOIN matches m ON s.match_id = m.match_id 
        WHERE m.team1_id = %s OR m.team2_id = %s
    """, (team_id, team_id))
    scores = cur.fetchall()

    cur.close()

    if team:
        return render_template('team_profile.html', team=team, players=players, scores=scores)
    else:
        flash('Team not found', 'error')
        return redirect(url_for('search'))

@app.route('/player/<int:player_id>')
def player_profile(player_id):
    db = get_db()
    cur = db.cursor()

    # Get player details along with team
    cur.execute("""
        SELECT p.name, p.age, p.position, t.team_id, t.name AS team_name 
        FROM players p 
        JOIN teams t ON p.team_id = t.team_id 
        WHERE p.player_id = %s
    """, (player_id,))
    player = cur.fetchone()
    cur.close()

    if player:
        return render_template('player_profile.html', player=player)
    else:
        flash('Player not found', 'error')
        return redirect(url_for('search'))


@app.route('/admin')
def admin():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))
    return render_template('admin.html')

@app.route('/user')
def user():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    cur = db.cursor()
    cur.execute('SELECT * FROM users;')
    users = cur.fetchall()
    cur.close()
    return render_template('user.html', users=users)

@app.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            db = get_db()
            cur = db.cursor()
            username = request.form['username']
            password = request.form['password']
            email = request.form['email']
            cur.execute(
                'INSERT INTO users (username, password, email) VALUES (%s, %s, %s)',
                (username, password, email))
            db.commit()
            cur.close()
            flash('User added successfully', 'success')
            return redirect(url_for('user'))
        except Exception as e:
            db.rollback()
            print("Error: ", str(e))
            flash('Failed to add user', 'error')
            return redirect(url_for('add_user'))
    return render_template('add_user.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    db = get_db()
    cur = db.cursor()
    user_id = session['user_id']

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Check if the username already exists
        cur.execute('SELECT * FROM users WHERE username = %s AND user_id != %s', (username, user_id))
        existing_user = cur.fetchone()
        if existing_user:
            flash('Username already taken', 'error')
            return redirect(url_for('profile'))

        # Check if the email already exists
        cur.execute('SELECT * FROM users WHERE email = %s AND user_id != %s', (email, user_id))
        existing_email = cur.fetchone()
        if existing_email:
            flash('Email already registered', 'error')
            return redirect(url_for('profile'))

        cur.execute('UPDATE users SET username = %s, email = %s, password = %s WHERE user_id = %s',
                    (username, email, password, user_id))
        db.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))

    cur.execute('SELECT username, email FROM users WHERE user_id = %s', (user_id,))
    user = cur.fetchone()
    cur.close()

    return render_template('profile.html', user=user)


if __name__ == '__main__':
    app.run(debug=True)
