from models import db, User

class AuthService:
    @staticmethod
    def login(email, password):
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            return user
        return None

    @staticmethod
    def register(rut, email, full_name, password):
        existing_user = User.query.filter_by(rut=rut).first()
        if existing_user:
            return None  # User already exists
        
        if User.query.filter_by(email=email).first():
            return None # Email used
        
        new_user = User(rut=rut, email=email, full_name=full_name)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return new_user
