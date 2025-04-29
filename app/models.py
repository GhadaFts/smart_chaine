from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Shift(db.Model):
    __tablename__ = 'shift'
    id = db.Column(db.Integer, primary_key=True)
    heureDebut = db.Column(db.String(50), nullable=False)
    heureFin = db.Column(db.String(50), nullable=False)
    nombreCablesHeure = db.Column(db.Integer, nullable=False)
    pourcentageCablesHeure = db.Column(db.Float, nullable=False)
    nombreCablesShift = db.Column(db.Integer, nullable=False)
    pourcentageCablesShift = db.Column(db.Float, nullable=False)
    nomChef = db.Column(db.String(100), nullable=False)
    motDePasseChef = db.Column(db.String(100), nullable=False)

    postes = db.relationship('Poste', backref='shift', lazy=True)
    productions_horaires = db.relationship('ProductionHoraire', backref='shift', lazy=True)

    def __repr__(self):
        return f"Shift {self.id}: {self.heureDebut} - {self.heureFin}, Chef: {self.nomChef}"


class ProductionHoraire(db.Model):
    __tablename__ = 'production_horaire'
    id = db.Column(db.Integer, primary_key=True)
    heure = db.Column(db.String(5), nullable=False)  # Ex: "06:00"
    nombreCables = db.Column(db.Integer, nullable=False)

    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=False)


class Poste(db.Model):
    __tablename__ = 'poste'
    id = db.Column(db.Integer, primary_key=True)
    numPoste = db.Column(db.Integer, nullable=False)
    nomPorteurPoste = db.Column(db.String(100), nullable=False)

    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=False)
    arrets = db.relationship('Arret', backref='poste', lazy=True)

    def __repr__(self):
        return f"Poste {self.numPoste} - {self.nomPorteurPoste}"


class Arret(db.Model):
    __tablename__ = 'arret'
    id = db.Column(db.Integer, primary_key=True)
    debut = db.Column(db.String(50), nullable=False)
    duree = db.Column(db.String(50), nullable=False)

    poste_id = db.Column(db.Integer, db.ForeignKey('poste.id'), nullable=False)

    def __repr__(self):
        return f'<Arret {self.id} - {self.debut} ({self.duree})>'
