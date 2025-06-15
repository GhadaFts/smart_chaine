import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
import re
import requests
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy

# Configurer le logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:postgressqlGhada@localhost:5432/smartChaine2'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modèles
class Shift(db.Model):
    __tablename__ = 'shift'
    id = db.Column(db.Integer, primary_key=True)
    heureDebut = db.Column(db.String(5), nullable=False)
    heureFin = db.Column(db.String(5), nullable=False)
    cable_count = db.Column(db.Integer, default=0)
    cb_per_hour = db.Column(db.Integer, default=0)
    cb_per_shift = db.Column(db.Integer, default=0)
    nomChef = db.Column(db.String(100), nullable=False)
    motDePasseChef = db.Column(db.String(100), nullable=False)
    postes = db.relationship('Poste', backref='shift', lazy=True)
    productions_horaires = db.relationship('ProductionHoraire', backref='shift', lazy=True)
    last_processed_timestamp = db.Column(db.DateTime(timezone=True))

class Poste(db.Model):
    __tablename__ = 'poste'
    id = db.Column(db.Integer, primary_key=True)
    numPoste = db.Column(db.Integer, nullable=False)
    nomPorteurPoste = db.Column(db.String(100), nullable=False)
    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=False)
    arrets = db.relationship('Arret', backref='poste', lazy=True)

class Arret(db.Model):
    __tablename__ = 'arret'
    id = db.Column(db.Integer, primary_key=True)
    debut = db.Column(db.DateTime(timezone=True), nullable=False)
    duree = db.Column(db.Integer, nullable=False)
    poste_id = db.Column(db.Integer, db.ForeignKey('poste.id'), nullable=False)
    firebase_record_id = db.Column(db.String(100), unique=True)

class ProductionHoraire(db.Model):
    __tablename__ = 'production_horaire'
    id = db.Column(db.Integer, primary_key=True)
    heure = db.Column(db.DateTime(timezone=True), nullable=False)
    nombreCables = db.Column(db.Integer, nullable=False)
    shift_id = db.Column(db.Integer, db.ForeignKey('shift.id'), nullable=False)

# Configuration Firebase
FIREBASE_URL = "https://sinda-34c14-default-rtdb.firebaseio.com/production/logs.json"

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
        
        # Réinitialiser les attributs si le shift n'est pas en travail
        if not en_travail:
            s.cable_count = 0
            s.cb_per_hour = 0
            s.cb_per_shift = 0
            s.nomChef = "Inactif"
            for poste in s.postes:
                for arret in poste.arrets[:]:
                    db.session.delete(arret)
            for production in s.productions_horaires[:]:
                db.session.delete(production)
            logger.info(f"Shift {s.id} non en travail : attributs réinitialisés, arrêts et productions supprimés")
        
        heures_production = [p.heure.strftime('%H:%M') for p in s.productions_horaires]
        cables_par_heure = [p.nombreCables for p in s.productions_horaires]
        
        shifts.append({
            'id': s.id,
            'heureDebut': s.heureDebut,
            'heureFin': s.heureFin,
            'nombreCablesHeure': s.cb_per_hour,
            'nombreCablesShift': s.cb_per_shift,
            'nombreCablesFinis': s.cable_count,
            'enTravail': en_travail,
            'heures_production': heures_production,
            'cables_par_heure': cables_par_heure,
            'postes': [
                {
                    'numPoste': p.numPoste,
                    'nomPoste': p.nomPorteurPoste,
                    'arrets': [
                        {'debut': a.debut.strftime('%H:%M'), 'duree': a.duree} for a in p.arrets
                    ]
                }
                for p in s.postes
            ]
        })
    
    db.session.commit()
    return render_template('suivi.html', shifts=shifts)

@app.route('/add_shift_data')
def add_shift_data():
    from faker import Faker
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
            cable_count=0,
            cb_per_hour=0,
            cb_per_shift=0,
            nomChef=fake.name(),
            motDePasseChef=fake.password(),
            last_processed_timestamp=datetime.now(timezone.utc) - timedelta(days=1)
        )
        db.session.add(shift)
        db.session.flush()

        for i in range(1, 9):
            poste = Poste(
                numPoste=i,
                nomPorteurPoste=fake.name(),
                shift_id=shift.id
            )
            db.session.add(poste)

    db.session.commit()
    return "Shifts et postes créés!"

@app.route('/reset_shift', methods=['POST'])
def reset_shift():
    with app.app_context():
        current_shift = find_current_shift()
        if not current_shift:
            logger.warning("Aucun shift en cours pour réinitialisation")
            return jsonify({"status": "error", "message": "Aucun shift en cours"}), 400
        
        # Réinitialiser les attributs
        current_shift.cable_count = 0
        current_shift.cb_per_hour = 0
        current_shift.cb_per_shift = 0
        
        # Supprimer les arrêts
        for poste in current_shift.postes:
            for arret in poste.arrets[:]:
                db.session.delete(arret)
        
        # Supprimer les productions
        for production in current_shift.productions_horaires[:]:
            db.session.delete(production)
        
        db.session.commit()
        logger.info(f"Shift {current_shift.id} réinitialisé : attributs à 0, arrêts et productions supprimés")
        return jsonify({"status": "success", "message": f"Shift {current_shift.id} réinitialisé avec succès"})

def find_current_shift():
    now = datetime.now().time()
    shifts = Shift.query.all()
    
    for shift in shifts:
        try:
            heure_debut = datetime.strptime(shift.heureDebut, '%H:%M').time()
            heure_fin = datetime.strptime(shift.heureFin, '%H:%M').time()
            
            if heure_debut < heure_fin:
                if heure_debut <= now <= heure_fin:
                    return shift
            else:
                if now >= heure_debut or now <= heure_fin:
                    return shift
        except Exception as e:
            logger.error(f"Erreur dans find_current_shift pour shift {shift.id}: {str(e)}")
    
    logger.warning("Aucun shift en cours trouvé")
    return None

def parse_timestamp(ts):
    if not ts:
        return datetime.now(timezone.utc)
    
    try:
        if re.match(r'^\d{8}_\d{6}$', ts):
            return datetime.strptime(ts, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
        
        if ts.isdigit():
            ts_int = int(ts)
            if ts_int > 1e10:
                ts_int //= 1000
            return datetime.fromtimestamp(ts_int, tz=timezone.utc)
        
        try:
            parsed_time = datetime.strptime(ts, "%H:%M:%S").time()
            return datetime.combine(datetime.today(), parsed_time, tzinfo=timezone.utc)
        except:
            parsed_time = datetime.strptime(ts, "%H:%M").time()
            return datetime.combine(datetime.today(), parsed_time, tzinfo=timezone.utc)
            
    except Exception as e:
        logger.error(f"Erreur de conversion du timestamp: {ts}, {str(e)}")
    
    logger.warning(f"Format de timestamp non reconnu: {ts}, utilisation de la date actuelle")
    return datetime.now(timezone.utc)

def process_record(shift, timestamp_key, record, firebase_id):
    try:
        record_timestamp = parse_timestamp(timestamp_key)
        
        if record_timestamp <= shift.last_processed_timestamp:
            logger.debug(f"Enregistrement {timestamp_key} déjà traité - ignoré")
            return False
        
        if 'cable_count' in record:
            shift.cable_count = record['cable_count']
        if 'cb_per_hour' in record:
            shift.cb_per_hour = record['cb_per_hour']
        if 'cb_per_shift' in record:
            shift.cb_per_shift = record['cb_per_shift']
        
        shift.last_processed_timestamp = record_timestamp
        
        logger.debug(f"Inspection de l'enregistrement: jigs={record.get('jigs')}, durees={record.get('durees')}")
        
        if 'jigs' in record and record['jigs'] != '0':
            try:
                existing_arret = Arret.query.filter_by(firebase_record_id=firebase_id).first()
                if existing_arret:
                    logger.debug(f"Arrêt {firebase_id} existe déjà - ignoré")
                    return True
                
                poste_num = int(record['jigs'])
                logger.debug(f"Poste num: {poste_num}")
                
                poste = Poste.query.filter_by(
                    numPoste=poste_num, 
                    shift_id=shift.id
                ).first()
                
                if not poste:
                    poste = Poste(
                        numPoste=poste_num,
                        nomPorteurPoste=f"Porteur {poste_num}",
                        shift_id=shift.id
                    )
                    db.session.add(poste)
                    db.session.commit()
                    logger.info(f"Poste créé: {poste_num} pour shift {shift.id}")
                
                durees = record.get('durees', {})
                duree = durees.get(f'jig{poste_num}', 0)
                logger.debug(f"Durée pour jig{poste_num}: {duree}")
                
                try:
                    arret = Arret(
                        debut=record_timestamp,
                        duree=duree,
                        poste_id=poste.id,
                        firebase_record_id=firebase_id
                    )
                    db.session.add(arret)
                    logger.info(f"Nouvel arrêt enregistré pour le poste {poste_num}: {duree} secondes, firebase_id={firebase_id}")
                except Exception as e:
                    logger.error(f"Erreur lors de l'enregistrement de Arret: {str(e)}", exc_info=True)
                    db.session.rollback()
                    return False
            
            except (ValueError, TypeError) as e:
                logger.error(f"Erreur de traitement pour jigs: {record.get('jigs')}, {str(e)}")
                return False
        
        else:
            logger.debug("Aucun arrêt à enregistrer: jigs absent ou égal à '0'")
        
        return True
    
    except Exception as e:
        logger.error(f"Erreur dans process_record: {str(e)}", exc_info=True)
        db.session.rollback()
        return False

def process_firebase_data(data):
    try:
        with app.app_context():
            current_shift = find_current_shift()
            if not current_shift:
                logger.warning("Aucun shift en cours - arrêt du traitement")
                return
            
            logger.info(f"Shift en cours trouvé: {current_shift.id}")
            
            logger.debug(f"Données brutes reçues de Firebase: {data}")
            logger.debug(f"Clés reçues de Firebase: {list(data.keys())}")
            
            timestamp_keys = [key for key in data.keys() if re.match(r'^\d{8}_\d{6}$', key)]
            if not timestamp_keys:
                logger.warning("Aucun timestamp valide trouvé dans les données Firebase")
                return
            
            latest_timestamp = max(timestamp_keys)
            record_timestamp = parse_timestamp(latest_timestamp)
            
            last_processed = current_shift.last_processed_timestamp
            if last_processed and last_processed.tzinfo is None:
                last_processed = last_processed.replace(tzinfo=timezone.utc)
            
            if last_processed and record_timestamp <= last_processed:
                logger.debug(f"Le dernier enregistrement {latest_timestamp} est déjà traité")
                return
            
            records_dict = data[latest_timestamp]
            
            if not isinstance(records_dict, dict):
                logger.warning(f"Les données pour {latest_timestamp} ne sont pas un dictionnaire - ignoré")
                return
            
            logger.info(f"Traitement de l'enregistrement pour le timestamp: {latest_timestamp}")
            
            processed_records = 0
            new_arrets = 0
            initial_cable_count = db.session.query(Shift.cable_count).filter_by(id=current_shift.id).scalar()
            
            for firebase_id, record in records_dict.items():
                if process_record(current_shift, latest_timestamp, record, firebase_id):
                    processed_records += 1
                    if 'jigs' in record and record['jigs'] != '0':
                        new_arrets += 1
            
            new_cable_count = current_shift.cable_count
            old_cable_count = initial_cable_count or 0
            production_difference = new_cable_count - old_cable_count

            if production_difference > 0:
                try:
                    production = ProductionHoraire(
                        heure=datetime.now(timezone.utc),
                        nombreCables=production_difference,
                        shift_id=current_shift.id
                    )
                    db.session.add(production)
                    logger.info(f"Production enregistrée: +{production_difference} câbles")
                except Exception as e:
                    logger.error(f"Erreur lors de l'enregistrement de ProductionHoraire: {str(e)}", exc_info=True)
                    db.session.rollback()
            
            db.session.commit()
            logger.info(f"Shift {current_shift.id} mis à jour. Enregistrements traités: {processed_records}, Nouveaux arrêts: {new_arrets}")
    
    except Exception as e:
        logger.error(f"Erreur dans process_firebase_data: {str(e)}", exc_info=True)
        db.session.rollback()

def firebase_listener():
    logger.info("Démarrage du listener Firebase")
    
    while True:
        try:
            response = requests.get(FIREBASE_URL)
            data = response.json()
            
            if data:
                logger.info("Données reçues de Firebase")
                process_firebase_data(data)
            else:
                logger.info("Aucune donnée reçue de Firebase")
            
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"Erreur Firebase: {str(e)}", exc_info=True)
            time.sleep(5)

def start_firebase_listener():
    logger.info("Initialisation de l'application")
    
    with app.app_context():
        db.create_all()
        
        shifts = Shift.query.all()
        for shift in shifts:
            if shift.last_processed_timestamp is None:
                shift.last_processed_timestamp = datetime.now(timezone.utc) - timedelta(days=1)
                logger.info(f"Initialisation du timestamp pour shift {shift.id}")
        
        db.session.commit()
    
    if not hasattr(app, 'firebase_thread_running'):
        app.firebase_thread_running = True
        thread = threading.Thread(target=firebase_listener)
        thread.daemon = True
        thread.start()
        logger.info("Thread Firebase démarré")

if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
    start_firebase_listener()

else:
    @app.before_first_request
    def init_before_first_request():
        start_firebase_listener()

if __name__ == '__main__':
    app.run(debug=True)