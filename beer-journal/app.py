import os, csv, io, secrets
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, flash, session, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
from sqlalchemy import func, or_

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///beerjournal-dev.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024))
app.config["UPLOAD_FOLDER"] = os.environ.get("UPLOAD_FOLDER", os.path.join(app.root_path, "uploads"))
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"

beer_tags = db.Table(
    "beer_tags",
    db.Column("beer_id", db.Integer, db.ForeignKey("beer.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    beers = db.relationship("Beer", backref="owner", cascade="all, delete-orphan")
    breweries = db.relationship("Brewery", backref="owner", cascade="all, delete-orphan")
    wishlist_items = db.relationship("Wishlist", backref="owner", cascade="all, delete-orphan")
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    revoked_at = db.Column(db.DateTime)
    creator = db.relationship("User", foreign_keys=[created_by_id])

class Brewery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(160), default="")
    country = db.Column(db.String(80), default="")
    website = db.Column(db.String(255), default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    beers = db.relationship("Beer", backref="brewery", lazy=True)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(40), nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "name", name="uq_user_tag"),)

class Beer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    brewery_id = db.Column(db.Integer, db.ForeignKey("brewery.id"))
    name = db.Column(db.String(140), nullable=False)
    style = db.Column(db.String(80), default="")
    abv = db.Column(db.Float)
    ibu = db.Column(db.Integer)
    serving_temp = db.Column(db.String(40), default="")
    rating = db.Column(db.Float, nullable=False, default=5.0)
    tasting_notes = db.Column(db.Text, default="")
    image_filename = db.Column(db.String(255))
    tasted_on = db.Column(db.Date, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tags = db.relationship("Tag", secondary=beer_tags, lazy="joined")

class Wishlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    beer_name = db.Column(db.String(140), nullable=False)
    brewery_name = db.Column(db.String(120), default="")
    style = db.Column(db.String(80), default="")
    notes = db.Column(db.Text, default="")
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

TRANSLATIONS = {
 "en": {
  "dashboard":"Dashboard","reviews":"My reviews","add_beer":"Add a beer","wishlist":"Wishlist","breweries":"Breweries","stats":"Statistics","export":"Export CSV","logout":"Log out","login":"Log in","register":"Create account","username":"Username","email":"Email","password":"Password","welcome":"Your personal beer tasting journal","tasted":"Beers tasted","average":"Average rating","wishlisted":"On wishlist","recent":"Recent reviews","search":"Search beers or breweries","all_styles":"All styles","all_tags":"All flavours","filter":"Filter","beer":"Beer","brewery":"Brewery","style":"Style","abv":"ABV (%)","ibu":"IBU","temperature":"Serving temperature","rating":"Rating / 10","tasted_on":"Date tasted","flavours":"Flavour tags","notes":"Tasting notes","photo":"Beer photo","save":"Save beer","cancel":"Cancel","actions":"Actions","edit":"Edit","delete":"Delete","details":"Details","no_beers":"No reviews yet. Add your first beer!","brewery_details":"Brewery details","location":"Location","country":"Country","website":"Website","brewery_notes":"Brewery notes","add_brewery":"Add brewery","save_brewery":"Save brewery","wishlist_add":"Add to wishlist","name":"Name","notes":"Notes","remove":"Remove","chart_ratings":"Your rating distribution","chart_styles":"Beers by style","top_breweries":"Top breweries","no_data":"Not enough data yet","password_help":"Use at least 8 characters.","confirm_password":"Confirm password","account_exists":"Username or email already exists.","bad_login":"Invalid username/email or password.","signup_success":"Account created. Welcome!","beer_saved":"Beer review saved.","brewery_saved":"Brewery saved.","wishlist_saved":"Added to your wishlist.","lang":"Français","delete_confirm":"Are you sure?","all_ratings":"All ratings","min_rating":"Minimum rating","max_rating":"Maximum rating","no_breweries":"No breweries yet.","add_wishlist":"Add a wishlist beer","optional":"Optional","footer":"Taste • Review • Enjoy"
 },
 "fr": {
  "dashboard":"Tableau de bord","reviews":"Mes critiques","add_beer":"Ajouter une bière","wishlist":"À essayer","breweries":"Brasseries","stats":"Statistiques","export":"Exporter CSV","logout":"Déconnexion","login":"Connexion","register":"Créer un compte","username":"Nom d’utilisateur","email":"Courriel","password":"Mot de passe","welcome":"Votre carnet personnel de dégustation","tasted":"Bières dégustées","average":"Note moyenne","wishlisted":"Sur la liste","recent":"Critiques récentes","search":"Chercher une bière ou brasserie","all_styles":"Tous les styles","all_tags":"Toutes les saveurs","filter":"Filtrer","beer":"Bière","brewery":"Brasserie","style":"Style","abv":"Alcool (%)","ibu":"IBU","temperature":"Température de service","rating":"Note / 10","tasted_on":"Date dégustée","flavours":"Étiquettes de saveur","notes":"Notes de dégustation","photo":"Photo de la bière","save":"Enregistrer","cancel":"Annuler","actions":"Actions","edit":"Modifier","delete":"Supprimer","details":"Détails","no_beers":"Aucune critique. Ajoutez votre première bière!","brewery_details":"Détails de la brasserie","location":"Ville / région","country":"Pays","website":"Site web","brewery_notes":"Notes sur la brasserie","add_brewery":"Ajouter une brasserie","save_brewery":"Enregistrer la brasserie","wishlist_add":"Ajouter à la liste","name":"Nom","notes":"Notes","remove":"Retirer","chart_ratings":"Répartition de vos notes","chart_styles":"Bières par style","top_breweries":"Meilleures brasseries","no_data":"Pas encore assez de données","password_help":"Utilisez au moins 8 caractères.","confirm_password":"Confirmer le mot de passe","account_exists":"Ce nom d’utilisateur ou courriel existe déjà.","bad_login":"Nom d’utilisateur/courriel ou mot de passe invalide.","signup_success":"Compte créé. Bienvenue!","beer_saved":"Critique enregistrée.","brewery_saved":"Brasserie enregistrée.","wishlist_saved":"Ajouté à votre liste.","lang":"English","delete_confirm":"Êtes-vous certain?","all_ratings":"Toutes les notes","min_rating":"Note minimale","max_rating":"Note maximale","no_breweries":"Aucune brasserie.","add_wishlist":"Ajouter une bière à essayer","optional":"Facultatif","footer":"Déguster • Critiquer • Savourer"
 }
}
def tr(key): return TRANSLATIONS.get(session.get("lang","en"), TRANSLATIONS["en"]).get(key, key)
@app.context_processor
def inject_globals(): return {"t": tr, "lang": session.get("lang","en"), "today": date.today()}

def owned_beer(beer_id):
    beer = db.session.get(Beer, beer_id)
    if not beer or beer.user_id != current_user.id: abort(404)
    return beer

def owned_brewery(brewery_id):
    brewery = db.session.get(Brewery, brewery_id)
    if not brewery or brewery.user_id != current_user.id: abort(404)
    return brewery

def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin: abort(403)
        return view(*args, **kwargs)
    return wrapped

def invitation_status(invite):
    now=datetime.utcnow()
    if invite.revoked_at: return "revoked"
    if invite.used_at: return "used"
    if invite.expires_at <= now: return "expired"
    return "pending"

@app.route("/language/<code>")
def language(code):
    if code in ("en","fr"): session["lang"] = code
    return redirect(request.referrer or url_for("dashboard"))

@app.route("/")
def home(): return redirect(url_for("dashboard") if current_user.is_authenticated else url_for("login"))

@app.route("/register", methods=["GET","POST"])
def register():
    return redirect(url_for("login"))

@app.route("/invite/<token>", methods=["GET","POST"])
def accept_invitation(token):
    import hashlib
    invite=Invitation.query.filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest()).first()
    if not invite or invitation_status(invite)!="pending":
        return render_template("invitation_invalid.html"),410
    if request.method=="POST":
        username=request.form.get("username","").strip(); email=request.form.get("email","").strip().lower()
        password=request.form.get("password",""); confirm=request.form.get("confirm_password","")
        if len(username)<3 or len(password)<8 or password!=confirm or not email:
            flash("Check your details: username 3+ chars, valid email, matching password (8+ chars).","warning")
        elif User.query.filter(or_(User.username==username,User.email==email)).first(): flash(tr("account_exists"),"danger")
        else:
            user=User(username=username,email=email); user.set_password(password)
            db.session.add(user); invite.used_at=datetime.utcnow(); db.session.commit(); login_user(user)
            flash(tr("signup_success"),"success"); return redirect(url_for("dashboard"))
    return render_template("accept_invitation.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if current_user.is_authenticated: return redirect(url_for("dashboard"))
    if request.method=="POST":
        ident=request.form.get("identity","").strip()
        user=User.query.filter(or_(func.lower(User.username)==ident.lower(),func.lower(User.email)==ident.lower())).first()
        if user and user.check_password(request.form.get("password","")):
            login_user(user); return redirect(url_for("dashboard"))
        flash(tr("bad_login"),"danger")
    return render_template("login.html")

@app.post("/logout")
@login_required
def logout(): logout_user(); return redirect(url_for("login"))

@app.route("/admin")
@admin_required
def admin():
    return render_template("admin.html", users=User.query.order_by(User.created_at.asc()).all(), invitations=Invitation.query.order_by(Invitation.created_at.desc()).all(), invitation_status=invitation_status)

@app.post("/admin/invitations/create")
@admin_required
def create_invitation():
    import hashlib
    token=secrets.token_urlsafe(32)
    invite=Invitation(token_hash=hashlib.sha256(token.encode()).hexdigest(),created_by_id=current_user.id,expires_at=datetime.utcnow()+__import__("datetime").timedelta(days=7))
    db.session.add(invite); db.session.commit()
    session["new_invitation_link"]=url_for("accept_invitation",token=token,_external=True)
    flash("Invitation created. Copy the link now; the full token is only shown once.","success")
    return redirect(url_for("admin"))

@app.post("/admin/invitations/<int:invite_id>/revoke")
@admin_required
def revoke_invitation(invite_id):
    invite=db.session.get(Invitation,invite_id)
    if not invite: abort(404)
    if invitation_status(invite)=="pending": invite.revoked_at=datetime.utcnow(); db.session.commit()
    return redirect(url_for("admin"))

@app.route("/dashboard")
@login_required
def dashboard():
    beers=Beer.query.filter_by(user_id=current_user.id).order_by(Beer.tasted_on.desc(),Beer.id.desc()).limit(6).all()
    count=Beer.query.filter_by(user_id=current_user.id).count()
    avg=db.session.query(func.avg(Beer.rating)).filter_by(user_id=current_user.id).scalar() or 0
    wish=Wishlist.query.filter_by(user_id=current_user.id).count()
    return render_template("dashboard.html", beers=beers,count=count,avg=avg,wish=wish)

def get_tags(raw):
    tags=[]
    for name in [x.strip() for x in raw.split(",") if x.strip()]:
        name=name[:40]
        tag=Tag.query.filter_by(user_id=current_user.id,name=name).first()
        if not tag: tag=Tag(user_id=current_user.id,name=name); db.session.add(tag)
        if tag not in tags: tags.append(tag)
    return tags

@app.route("/beers")
@login_required
def beers():
    q=Beer.query.filter_by(user_id=current_user.id)
    search=request.args.get("q","").strip()
    style=request.args.get("style","")
    tag=request.args.get("tag","")
    min_rating=request.args.get("min_rating","")
    if search: q=q.outerjoin(Brewery).filter(or_(Beer.name.ilike(f"%{search}%"),Brewery.name.ilike(f"%{search}%")))
    if style: q=q.filter(Beer.style==style)
    if tag: q=q.join(Beer.tags).filter(Tag.name==tag)
    if min_rating:
        try: q=q.filter(Beer.rating>=float(min_rating))
        except ValueError: pass
    order=request.args.get("sort","newest")
    if order=="rating": q=q.order_by(Beer.rating.desc())
    elif order=="oldest": q=q.order_by(Beer.tasted_on.asc())
    else: q=q.order_by(Beer.tasted_on.desc(),Beer.id.desc())
    items=q.all()
    styles=[x[0] for x in db.session.query(Beer.style).filter(Beer.user_id==current_user.id,Beer.style!="").distinct().order_by(Beer.style).all()]
    tags=Tag.query.filter_by(user_id=current_user.id).order_by(Tag.name).all()
    return render_template("beers.html",beers=items,styles=styles,tags=tags)

@app.route("/beer/new", methods=["GET","POST"])
@login_required
def beer_new(): return beer_form(None)

@app.route("/beer/<int:beer_id>/edit", methods=["GET","POST"])
@login_required
def beer_edit(beer_id): return beer_form(owned_beer(beer_id))

def beer_form(beer):
    breweries=Brewery.query.filter_by(user_id=current_user.id).order_by(Brewery.name).all()
    if request.method=="POST":
        name=request.form.get("name","").strip()
        try: rating=float(request.form.get("rating","5"))
        except ValueError: rating=-1
        if not name or rating<0 or rating>10 or round(rating*2)!=rating*2:
            flash("Enter a beer name and a rating from 0 to 10 in 0.5 increments.","danger")
            return render_template("beer_form.html",beer=beer,breweries=breweries)
        if beer is None: beer=Beer(user_id=current_user.id)
        beer.name=name[:140]; beer.style=request.form.get("style","")[:80]
        beer.abv=float(request.form["abv"]) if request.form.get("abv") else None
        beer.ibu=int(request.form["ibu"]) if request.form.get("ibu") else None
        beer.serving_temp=request.form.get("serving_temp","")[:40]
        beer.rating=rating; beer.tasting_notes=request.form.get("tasting_notes","")
        beer.tasted_on=date.fromisoformat(request.form["tasted_on"]) if request.form.get("tasted_on") else date.today()
        brewery_id=request.form.get("brewery_id")
        brewery=db.session.get(Brewery,int(brewery_id)) if brewery_id else None
        beer.brewery=brewery if brewery and brewery.user_id==current_user.id else None
        beer.tags=get_tags(request.form.get("tags",""))
        photo=request.files.get("photo")
        if photo and photo.filename:
            try:
                img=Image.open(photo.stream); img.verify()
                photo.stream.seek(0)
                img=Image.open(photo.stream); img.thumbnail((1400,1400))
                filename=secrets.token_hex(16)+".jpg"
                path=os.path.join(app.config["UPLOAD_FOLDER"],filename)
                img.convert("RGB").save(path,"JPEG",quality=88,optimize=True)
                beer.image_filename=filename
            except Exception:
                flash("That image could not be processed. Please use JPG, PNG or WebP.","warning")
        db.session.add(beer); db.session.commit(); flash(tr("beer_saved"),"success")
        return redirect(url_for("beer_detail",beer_id=beer.id))
    return render_template("beer_form.html",beer=beer,breweries=breweries)

@app.route("/beer/<int:beer_id>")
@login_required
def beer_detail(beer_id): return render_template("beer_detail.html",beer=owned_beer(beer_id))

@app.post("/beer/<int:beer_id>/delete")
@login_required
def beer_delete(beer_id):
    beer=owned_beer(beer_id); db.session.delete(beer); db.session.commit()
    flash("Review deleted.","success"); return redirect(url_for("beers"))

@app.route("/breweries",methods=["GET","POST"])
@login_required
def breweries():
    if request.method=="POST":
        name=request.form.get("name","").strip()
        if name:
            b=Brewery(user_id=current_user.id,name=name[:120],location=request.form.get("location","")[:160],
                country=request.form.get("country","")[:80],website=request.form.get("website","")[:255],
                notes=request.form.get("notes",""))
            db.session.add(b); db.session.commit(); flash(tr("brewery_saved"),"success")
        return redirect(url_for("breweries"))
    items=Brewery.query.filter_by(user_id=current_user.id).order_by(Brewery.name).all()
    return render_template("breweries.html",breweries=items)

@app.post("/brewery/<int:brewery_id>/delete")
@login_required
def brewery_delete(brewery_id):
    b=owned_brewery(brewery_id)
    for beer in b.beers: beer.brewery=None
    db.session.delete(b); db.session.commit()
    return redirect(url_for("breweries"))

@app.route("/wishlist",methods=["GET","POST"])
@login_required
def wishlist():
    if request.method=="POST":
        name=request.form.get("beer_name","").strip()
        if name:
            db.session.add(Wishlist(user_id=current_user.id,beer_name=name[:140],
                brewery_name=request.form.get("brewery_name","")[:120],style=request.form.get("style","")[:80],
                notes=request.form.get("notes","")))
            db.session.commit(); flash(tr("wishlist_saved"),"success")
        return redirect(url_for("wishlist"))
    items=Wishlist.query.filter_by(user_id=current_user.id).order_by(Wishlist.added_at.desc()).all()
    return render_template("wishlist.html",items=items)

@app.post("/wishlist/<int:item_id>/delete")
@login_required
def wishlist_delete(item_id):
    item=db.session.get(Wishlist,item_id)
    if not item or item.user_id!=current_user.id: abort(404)
    db.session.delete(item); db.session.commit(); return redirect(url_for("wishlist"))

@app.route("/stats")
@login_required
def stats():
    items=Beer.query.filter_by(user_id=current_user.id).all()
    ratings={str(x/2):sum(1 for b in items if b.rating==x/2) for x in range(0,21)}
    styles={}
    for b in items: styles[b.style or "Unspecified"]=styles.get(b.style or "Unspecified",0)+1
    top=db.session.query(Brewery.name,func.count(Beer.id).label("n"),func.avg(Beer.rating).label("avg")).join(Beer).filter(Beer.user_id==current_user.id).group_by(Brewery.id).order_by(func.avg(Beer.rating).desc()).limit(5).all()
    return render_template("stats.html",count=len(items),avg=(sum(b.rating for b in items)/len(items) if items else 0),
        ratings=ratings,styles=styles,top=top)

@app.route("/export.csv")
@login_required
def export_csv():
    output=io.StringIO(); writer=csv.writer(output)
    writer.writerow(["Beer","Brewery","Style","ABV","IBU","Serving temperature","Rating / 10","Tasted on","Flavour tags","Tasting notes"])
    for b in Beer.query.filter_by(user_id=current_user.id).order_by(Beer.tasted_on.desc()).all():
        writer.writerow([b.name,b.brewery.name if b.brewery else "",b.style,b.abv,b.ibu,b.serving_temp,b.rating,b.tasted_on.isoformat(),", ".join(t.name for t in b.tags),b.tasting_notes])
    data=io.BytesIO(("\ufeff"+output.getvalue()).encode("utf-8")); data.seek(0)
    return send_file(data,mimetype="text/csv; charset=utf-8",as_attachment=True,download_name="beer-journal-reviews.csv")

@app.route("/uploads/<filename>")
@login_required
def uploaded_file(filename):
    # Files are only served to authenticated users; filenames are random and never user supplied.
    from flask import send_from_directory
    return send_from_directory(app.config["UPLOAD_FOLDER"],filename)

@app.errorhandler(413)
def too_large(_): return "Image too large. Maximum upload size is 10 MB.",413

with app.app_context():
    db.create_all()
    from sqlalchemy import inspect, text
    cols={c["name"] for c in inspect(db.engine).get_columns("user")}
    if "is_admin" not in cols:
        db.session.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")); db.session.commit()
    if not User.query.filter_by(is_admin=True).first():
        first=User.query.order_by(User.id.asc()).first()
        if first: first.is_admin=True; db.session.commit()
        else:
            au=os.environ.get("ADMIN_USERNAME","").strip(); ae=os.environ.get("ADMIN_EMAIL","").strip().lower(); ap=os.environ.get("ADMIN_PASSWORD","")
            if au and ae and len(ap)>=12:
                u=User(username=au,email=ae,is_admin=True); u.set_password(ap); db.session.add(u); db.session.commit()
            else: app.logger.warning("Set ADMIN_USERNAME, ADMIN_EMAIL and ADMIN_PASSWORD (12+ chars) in .env to create the initial administrator.")

if __name__=="__main__":
    app.run(host="0.0.0.0",port=5000)
