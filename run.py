from app import create_app

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        from app.models import db
        db.create_all()  # Garante que as tabelas serão criadas
    app.run(debug=True)
