from datetime import date
import json
from flask import Flask, make_response, redirect, render_template, request
from functools import lru_cache
import subprocess
import re
import time
from datetime import datetime
from threading import Timer

supported_books = ["fanduel",  "draftkings", "betmgm", "pointsbet", "caesars", "wynn", "bet_rivers_ny"]

@lru_cache(maxsize=None)
def fetch_book(ttl_hash=None, book="fanduel", game=""):
    del ttl_hash
    return fetch_game_data(sportsbook=book, game=game)

def fetch_game_data(sportsbook="fanduel", game=""):
    cmd = ["python", "main.py", "-xgb", f"-odds={sportsbook}"]
    if not game == "":
        cmd.append(f"-game={game}")
    stdout = subprocess.check_output(cmd, cwd="../", shell=False, stderr=subprocess.DEVNULL).decode()
    data_re = re.compile(r'\n(?P<home_team>[\w ]+)(\((?P<home_confidence>[\d+\.]+)%\))? vs (?P<away_team>[\w ]+)(\((?P<away_confidence>[\d+\.]+)%\))?: (?P<ou_pick>OVER|UNDER) (?P<ou_value>[\d+\.]+) (\((?P<ou_confidence>[\d+\.]+)%\))?', re.MULTILINE)
    ev_re = re.compile(r'(?P<team>[\w ]+) EV: (?P<ev>[-\d+\.]+)', re.MULTILINE)
    odds_re = re.compile(r'(?P<away_team>[\w ]+) \((?P<away_team_odds>-?\d+)\) @ (?P<home_team>[\w ]+) \((?P<home_team_odds>-?\d+)\)', re.MULTILINE)
    games = {}
    for match in data_re.finditer(stdout):
        game_dict = {'away_team': match.group('away_team').strip(),
                     'home_team': match.group('home_team').strip(),
                     'away_confidence': match.group('away_confidence'),
                     'home_confidence': match.group('home_confidence'),
                     'ou_pick': match.group('ou_pick'),
                     'ou_value': match.group('ou_value'),
                     'ou_confidence': match.group('ou_confidence')}
        for ev_match in ev_re.finditer(stdout):
            if ev_match.group('team') == game_dict['away_team']:
                game_dict['away_team_ev'] = ev_match.group('ev')
            if ev_match.group('team') == game_dict['home_team']:
                game_dict['home_team_ev'] = ev_match.group('ev')
        for odds_match in odds_re.finditer(stdout):
            if odds_match.group('away_team') == game_dict['away_team']:
                game_dict['away_team_odds'] = odds_match.group('away_team_odds')
            if odds_match.group('home_team') == game_dict['home_team']:
                game_dict['home_team_odds'] = odds_match.group('home_team_odds')
        games[f"{game_dict['away_team']}:{game_dict['home_team']}"] = game_dict
    return games

def get_ttl_hash(seconds=600):
    """Return the same value withing `seconds` time period"""
    return round(time.time() / seconds)

def update_cache():
    fetch_book.cache_clear()
    fanduel = fetch_book(ttl_hash=get_ttl_hash())
    for game in fanduel.keys():
        for sportsbook in supported_books:
            print(f"{sportsbook} -> {game}")
            fetch_book(ttl_hash=get_ttl_hash(), game=":".join(game.split(":")[::-1]), book=sportsbook)
    x=datetime.today()
    y=x.replace(day=x.
    day+1, hour=0, minute=0, second=0, microsecond=0)
    delta_t=y-x
    secs=delta_t.seconds+1
    t = Timer(secs, update_cache)
    t.start()

def get_req_value(v):
    return request.args.get(v) if request.args.get(v) is not None else request.cookies.get(v)

def add_user(username, password, admin):
    with open("userlist.json") as f:
        js = json.load(f)
    js[username] = {"password": password, "admin": admin}
    with open("userlist.json", "w+") as f:
        js = json.dump(js, f)

def delete_user(username):
    with open("userlist.json") as f:
        js = json.load(f)
    del js[username]
    with open("userlist.json", "w+") as f:
        js = json.dump(js, f)

def check_username():
    username = get_req_value("username")
    password = get_req_value("password")
    with open("userlist.json") as f:
        js = json.load(f)
        try:
            if js[username]["password"] == password:
                return True, js[username]["admin"], username, password
            else:
                return False, False, username, password
        except:
            return False, False, username, password

def get_userlist():
    with open("userlist.json") as f:
        d = []
        for k, v in json.load(f).items():
            d.append({"username": k, "password":v["password"], "admin": v["admin"]})
        return d
Timer(5, update_cache).start()
app = Flask(__name__)
app.jinja_env.add_extension('jinja2.ext.loopcontrols')


@app.route("/list")
@app.route("/index.html")
@app.route("/")
def index():
    log, admin, username, password = check_username()
    if not log:
        if request.args.get("username") is not None and request.args.get("username")!="":
            return render_template("login_fail.html")
        else:
            return render_template("login.html")
    fanduel = fetch_book(ttl_hash=get_ttl_hash())
    resp = make_response(render_template('list.html', today=date.today(), data={"fanduel": fanduel}, admin=admin))
    resp.set_cookie("username", username)
    resp.set_cookie("password", password)
    return resp

@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/game")
def see_game():
    log, admin, username, password = check_username()
    if not log:
        if request.args.get("username") is not None and request.args.get("username")!="":
            return render_template("login_fail.html")
        else:
            return render_template("login.html")
    game = request.args.get("game")
    books = {}
    for sportsbook in supported_books:
        try:
            books[sportsbook] = fetch_book(ttl_hash=get_ttl_hash(), game=game, book=sportsbook)
            books[sportsbook] =  books[sportsbook][list(books[sportsbook].keys())[0]]
        except:
            del books[sportsbook]

    return render_template('game.html', today=date.today(), data=books, sportsbooks=list(books.keys()))

@app.route("/admin")
def admin_panel():
    log, admin, username, password = check_username()
    if (not log) or (not admin):
        return render_template("login_fail.html")
    return render_template('admin.html', users=get_userlist(), me=username)

@app.route("/admin_delete")
def del_user():
    log, admin, username, password = check_username()
    if (not log) or (not admin):
        return render_template("login_fail.html")
    if  request.args.get("user") != username:
        delete_user(request.args.get("user"))
    return redirect("/admin", code=302)

@app.route("/admin_create")
def create_user():
    log, admin, username, password = check_username()
    if (not log) or (not admin):
        return render_template("login_fail.html")
    if  request.args.get("user") != username:
        add_user(request.args.get("user"), request.args.get("pw"), False)
    return redirect("/admin", code=302)