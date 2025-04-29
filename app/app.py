from flask import Flask,render_template
from flask_sqlalchemy import SQLAlchemy
from faker import Faker
from models import db, Shift, Poste, Arret ,ProductionHoraire  # Importer les modèles depuis models.py
from datetime import datetime, timedelta


# Initialisation de l'application Flask
app = Flask(__name__)

# Configuration de la base de données
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:postgressqlGhada@localhost:5432/smartChaine2'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialisation de la base de données avec l'app Flask
db.init_app(app)

@app.route('/')
def landing():
    return render_template('home.html')


@app.route('/index')
def index():
    shifts = []

    now = datetime.now().time()

    for s in Shift.query.all():
        heure_debut = datetime.strptime(s.heureDebut, '%H:%M').time()
        heure_fin = datetime.strptime(s.heureFin, '%H:%M').time()

        en_travail = heure_debut <= now <= heure_fin if heure_debut < heure_fin else not (heure_fin < now < heure_debut)

        shifts.append({
            'id': s.id,
            'heureDebut': s.heureDebut,
            'heureFin': s.heureFin,
            'nombreCablesHeure': s.nombreCablesHeure,
            'pourcentageCablesHeure': s.pourcentageCablesHeure,
            'nombreCablesShift': s.nombreCablesShift,
            'pourcentageCablesShift': s.pourcentageCablesShift,
            'enTravail': en_travail,
            'heures_production': [p.heure for p in s.productions_horaires],
            'cables_par_heure': [p.nombreCables for p in s.productions_horaires],
            'postes': [
                {
                    'numPoste': p.numPoste,
                    'nomPoste': p.nomPorteurPoste,
                    'arrets': [
                        {'debut': a.debut, 'duree': a.duree} for a in p.arrets
                    ]
                }
                for p in s.postes
            ]
        })

    return render_template('suivi.html', shifts=shifts)


@app.route('/add_shift_data')
def add_shift_data():
    fake = Faker()

    shifts_data = [
        {"heureDebut": "06:00", "heureFin": "14:00"},
        {"heureDebut": "14:00", "heureFin": "22:00"},
        {"heureDebut": "22:00", "heureFin": "06:00"}
    ]

    for shift_data in shifts_data:
        shift = Shift(
            heureDebut=shift_data["heureDebut"],
            heureFin=shift_data["heureFin"],
            nombreCablesHeure=0,
            pourcentageCablesHeure=0,
            nombreCablesShift=0,
            pourcentageCablesShift=0,
            nomChef=fake.name(),
            motDePasseChef=fake.password()
        )
        db.session.add(shift)
        db.session.flush()  # Cela génère l'id du shift

        for i in range(8):
            poste = Poste(
                numPoste=i + 1,
                nomPorteurPoste=fake.name(),
                shift=shift
            )
            db.session.add(poste)

            for _ in range(3):
                arret = Arret(
                    debut=fake.time(),
                    duree=fake.time(),
                    poste=poste
                )
                db.session.add(arret)

        heure_debut_obj = datetime.strptime(shift_data["heureDebut"], '%H:%M')

        for h in range(8):
            heure_production = (heure_debut_obj + timedelta(hours=h)).time()

            production_horaire = ProductionHoraire(
                shift_id=shift.id,
                heure=heure_production.strftime('%H:%M'),
                nombreCables=fake.random_int(min=5, max=15)
            )
            db.session.add(production_horaire)

    db.session.commit()

    return "Shift, Postes, Arrêts et Productions horaires ajoutés!"


@app.route('/shifts')
def get_shifts():
    shifts = Shift.query.all()
    return '<br>'.join([str(shift) for shift in shifts])


from flask import request

@app.route('/update_production', methods=['POST'])
def update_production():
    data = request.get_json()

    shift_id = data.get('shift_id')
    nb_cables = data.get('nb_cables')

    shift = Shift.query.get(shift_id)
    if not shift:
        return "Shift not found", 404

    now = datetime.now().strftime("%H:%M")

    new_production = ProductionHoraire(
        heure=now,
        nombreCables=nb_cables,
        shift_id=shift.id
    )
    db.session.add(new_production)
    db.session.commit()

    # Mise à jour automatique du total dans shift
    total = sum(p.nombreCables for p in shift.productions_horaires)
    shift.nombreCablesShift = total
    shift.nombreCablesHeure = nb_cables
    db.session.commit()

    return {
        'message': f'Production ajoutée: {nb_cables} câbles à {now} pour Shift {shift_id}. Total shift = {total}',
        'shift_id': shift_id,
        'heure': now,
        'total_cables': total
    }

# Créer les tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)