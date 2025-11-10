from app import db


class Fakenodo(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    def __repr__(self):
        # Representación legible del objeto para depuración y logs.
        return f"Fakenodo<{self.id}>"
