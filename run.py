from app import create_app

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        # Garante que as tabelas serão criadas (incluindo 'papeis')
        # from app.models import db
        # db.create_all()         
    #app.run(debug=True)
        app.run(host='0.0.0.0', port=5000, debug=True)
