# ARCHIVED one-shot generator (session arena/7c532e8c-nba3).
# It produced the data/*.json files that were then hand-verified against the official PDFs.
# Do NOT re-run it to update data: it overwrites data/ and would discard later corrections.
# Edit data/*.json directly and run scripts/build_site.py.
import json
PDF="https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-11-13_05_00PM.pdf"
SCH="https://cdn.nba.com/manage/2026/08/2026-27-NBA-Regular-Season-Schedule-By-Date.pdf"
D13="2026-11-13"; D14="2026-11-14"
# attribution: R = matchup and team printed in row; S = team printed, matchup linked via official schedule pairing; U = team/matchup cell not extracted from PDF; T = team-level 'NOT YET SUBMITTED' row
rows=[]
def add(date,time,matchup,team,player,status,reason,attr,sched_matchup=None):
    rows.append(dict(game_date=date,game_time_et=time,matchup=matchup,team=team,player=player,status=status,reason_as_printed=reason,attribution=attr,schedule_source=(SCH if attr=="S" else None)))
# 11/13
add(D13,"07:00 (ET)","MIL@ORL","Orlando Magic","Banchero, Paolo","Out","Injury/Illness - Right High AnkleSprain","R")
add(D13,"07:00 (ET)","MIL@ORL","Orlando Magic","Cain, Jamal","Questionable","Injury/Illness - Left ShoulderContusion","R")
add(D13,"07:00 (ET)","MIL@ORL","Orlando Magic","da Silva, Tristan","Questionable","Injury/Illness - Left Calf Strain","R")
add(D13,"07:00 (ET)","MIL@ORL","Orlando Magic","Isaac, Jonathan","Out","Injury/Illness - Left Knee InjuryManagement","R")
add(D13,"07:00 (ET)","MIL@ORL","Orlando Magic","Nelson, Izaiyah","Out","Injury/Illness - Left Ankle InjuryRecovery","R")
add(D13,"07:00 (ET)","MIL@ORL","Orlando Magic","Penda, Noah","Out","Injury/Illness - Right Partially Torn Hamstring","R")
add(D13,"07:00 (ET)","MIL@ORL","Orlando Magic","Suggs, Jalen","Questionable","Injury/Illness - Right Knee Contusion/Bone Bruise","R")
add(D13,"07:00 (ET)","NYK@IND","Indiana Pacers","Furphy, Johnny","Out","Injury/Illness - Right ACL Repair/Surgery","R")
add(D13,"07:00 (ET)","NYK@IND","Indiana Pacers","Haliburton, Tyrese","Out","Injury/Illness - Left Hamstring Strain","R")
add(D13,"07:00 (ET)","NYK@IND","Indiana Pacers","McConnell, T.J.","Probable","Injury/Illness - Right Hamstring Strain","R")
add(D13,"07:00 (ET)","NYK@IND","Indiana Pacers","Nesmith, Aaron","Questionable","Injury/Illness - Right Knee Soreness","R")
add(D13,"07:00 (ET)","NYK@IND","Indiana Pacers","Sheppard, Ben","Out","Injury/Illness - Left Meniscus Surgery","R")
add(D13,"08:00 (ET)","ATL@CHI","Atlanta Hawks","Dennis, RayJ","Questionable","G League - Two-Way","R")
for p,s,r in [("Flemings, Kingston","Questionable","Injury/Illness - Lumbar Spasm"),("Gilbert, Keshon","Out","Injury/Illness - Left Knee Inflammation; Non-Surgical Procedure"),("Gueye, Mouhamed","Out","Injury/Illness - Left Foot Fracture"),("Landale, Jock","Available","Injury/Illness - Face Mask"),("Newell, Asa","Out","Injury/Illness - Left Great Toe Hyperextension"),("Veesaar, Henri","Out","Injury/Illness - Right ACL Tear"),("Wilson, Jalen","Out","G League - Two-Way")]:
    add(D13,"","","",p,s,r,"U")
for p,s,r in [("Awaka, Tobe","Out","Injury/Illness - Disc Irritation"),("Powell, Norman","Questionable","Injury/Illness - Low Back Spasms"),("Sellers, Jaylin","Out","G League - Two-Way"),("Swain, Dailyn","Questionable","Injury/Illness - Right Disc Irritation"),("Wilson, Caleb","Out","Injury/Illness - Right Metacarpal Fracture")]:
    add(D13,"08:00 (ET)","ATL@CHI","Chicago Bulls",p,s,r,"S")
for p,s,r in [("Diop, Khalifa","Out","G League - On Assignment"),("Merrill, Sam","Out","Injury/Illness - Right Elbow Injury Management"),("Mobley, Evan","Out","Injury/Illness - Left Great Toe - Sprain"),("Tomlin, Nae'Qwan","Out","Injury/Illness - Low Back Stress Reaction")]:
    add(D13,"","CLE@MIA","Cleveland Cavaliers",p,s,r,"R")
add(D13,"","","","Udeh, Jr., Ernest","Out","G League - Two-Way","U")
for p,s,r in [("Antetokounmpo, Giannis","Available","Injury/Illness - Right Wrist Sprain"),("Goldin, Vladislav","Out","G League - Two-Way"),("Larsson, Pelle","Doubtful","Injury/Illness - Illness"),("Thompson, Klay","Probable","Injury/Illness - Left Ankle Soreness")]:
    add(D13,"","CLE@MIA","Miami Heat",p,s,r,"S")
for p,s,r in [("Edey, Zach","Out","Injury/Illness - Left Ankle Injury Management"),("Lopez, Karim","Out","G League - On Assignment"),("Mashack, Jahmai","Out","G League - Two-Way"),("Pippen Jr., Scotty","Out","Injury/Illness - Lumbar Disc Herniation"),("Post, Quinten","Out","Injury/Illness - Concussion Protocol"),("Saunders, Richie","Out","Injury/Illness - Right Knee Surgery")]:
    add(D13,"","MEM@NOP","Memphis Grizzlies",p,s,r,"R")
for p,s,r in [("Dia, Malik","Available","G League - Two-Way"),("Mathurin, Bennedict","Questionable","Injury/Illness - Right Thumb Sprain"),("McGowens, Bryce","Out","Injury/Illness - Left Elbow Infection"),("Missi, Yves","Out","Injury/Illness - Left Knee Contusion / Bone Bruise"),("Murphy III, Trey","Out","Injury/Illness - Bilateral Patellar Tendinopathy"),("Murray, Dejounte","Out","Injury/Illness - Left Ankle Sprain")]:
    add(D13,"","MEM@NOP","New Orleans Pelicans",p,s,r,"R")
add(D13,"","","","Pierre Jr., Jaron","Available","G League - Two-Way","U")
add(D13,"","","","Watford, Trendon","Out","Injury/Illness - Right Ankle Sprain","U")
for p,s,r in [("Alexander, Trey","Out","G League - Two-Way"),("Bufkin, Kobe","Out","G League - Two-Way"),("Ingram, Harrison","Out","G League - Two-Way"),("Jackson Jr., Jaren","Out","Injury/Illness - Right MCL Tear"),("Markkanen, Lauri","Out","Injury/Illness - Right Hand Fracture"),("Nurkic, Jusuf","Out","Injury/Illness - Right 2nd Plantar Plate Tear")]:
    add(D13,"08:30 (ET)","UTA@HOU","Utah Jazz",p,s,r,"R")
for p,s,r in [("Adams, Steven","Out","Injury/Illness - Right Soleus Strain"),("Capela, Clint","Out","Injury/Illness - Right Ankle Sprain"),("Copeland, Quadir","Out","G League - Two-Way"),("Phillips, Julian","Out","G League - Two-Way"),("Smart, Marcus","Out","League Suspension")]:
    add(D13,"08:30 (ET)","UTA@HOU","Houston Rockets",p,s,r,"R")
for p,s,r in [("Bassey, Charles","Probable","Injury/Illness - Left Toe Soreness"),("Butler III, Jimmy","Out","Injury/Illness - Right ACL Repair / Surgery"),("Curry, Stephen","Out","Injury/Illness - Right Oblique Tear"),("Moody, Moses","Out","Injury/Illness - Left Patellar Tendon Repair / Surgery"),("Porzingis, Kristaps","Out","Not With Team")]:
    add(D13,"09:30 (ET)","GSW@SAS","Golden State Warriors",p,s,r,"R")
add(D13,"","","","Williams, Brandon","Out","Injury/Illness - Left Hamstring Strain","U")
for p,s,r in [("Fox, De'Aaron","Questionable","Injury/Illness - Left Hip Soreness"),("Harris, Tobias","Out","Injury/Illness - Left Calf Strain"),("Quaintance, Jayden","Out","Injury/Illness - Right Knee Surgery"),("Vassell, Devin","Questionable","Injury/Illness - Left Adductor Tightness")]:
    add(D13,"09:30 (ET)","GSW@SAS","San Antonio Spurs",p,s,r,"S")
for p,s,r in [("Krejci, Vit","Out","Injury/Illness - Left Ankle Fracture"),("Morant, Ja","Out","Injury/Illness - Left Hamstring Strain"),("Sharpe, Shaedon","Out","Injury/Illness - Right Meniscus Surgery"),("Youngblood, Chris","Out","Injury/Illness - Right Bone Bruise")]:
    add(D13,"10:00 (ET)","POR@SAC","Portland Trail Blazers",p,s,r,"R")
for p,s,r in [("Achiuwa, Precious","Out","Injury/Illness - Left Ankle Soreness"),("Karaban, Alex","Out","G League - On Assignment"),("Mogbo, Jonathan","Out","G League - Two-Way"),("Pedulla, Sean","Out","G League - Two-Way"),("Raynaud, Maxime","Out","Injury/Illness - Right Patella Subluxation"),("Simmons, Ben","Out","Injury/Illness - Right Achilles Tendon Repair / Surgery")]:
    add(D13,"10:00 (ET)","POR@SAC","Sacramento Kings",p,s,r,"R")
add(D13,"10:30 (ET)","OKC@LAC","Oklahoma City Thunder","Holmgren, Chet","Out","Injury/Illness - Right Knee/ Injury Recovery","R")
for p,s,r in [("Mitchell, Ajay","Questionable","Injury/Illness - Left Ankle Sprain"),("Sorber, Thomas","Out","Injury/Illness - Right Knee Surgery"),("Topic, Nikola","Available","-"),("Wallace, Cason","Out","Injury/Illness - Left Shoulder Surgery"),("Williams, Jalen","Out","Injury/Illness - Left Ankle Surgery"),("Williams, Jaylin","Out","Injury/Illness - Low Back Spasms")]:
    add(D13,"","","",p,s,r,"U")
for p,s,r in [("Beal, Bradley","Out","Injury/Illness - Right Knee Injury Management"),("Ingram, Brandon","Out","Injury/Illness - Right Heel Surgery"),("Martinelli, Nick","Out","G League - Two-Way"),("Miller, Jordan","Out","Injury/Illness - Left Rotator Cuff Surgery"),("Niederhauser, Yanic Konan","Out","Injury/Illness - Right Lisfranc Surgery")]:
    add(D13,"10:30 (ET)","OKC@LAC","LA Clippers",p,s,r,"S")
# 11/14
add(D14,"07:00 (ET)","DEN@NOP","Denver Nuggets","","NOT YET SUBMITTED","","T")
add(D14,"07:00 (ET)","DEN@NOP","New Orleans Pelicans","","NOT YET SUBMITTED","","T")
for p,s,r in [("Biberovic, Tarik","Out","Injury/Illness - Right Heel Bursitis"),("Christie, Max","Questionable","Injury/Illness - Left Ankle Sprain"),("de Larrea, Sergio","Out","Injury/Illness - Right Knee Sprain"),("Johnson Jr., Morez","Probable","Injury/Illness - Left Shin / Tibia Contusion"),("Lively II, Dereck","Out","Injury/Illness - Right Foot Surgery")]:
    add(D14,"07:30 (ET)","DAL@CLE","Dallas Mavericks",p,s,r,"R")
add(D14,"","","","Martin, Caleb","Available","Injury/Illness - Right Thumb Splint","U")
add(D14,"07:30 (ET)","DAL@CLE","Cleveland Cavaliers","","NOT YET SUBMITTED","","S")
for p,s,r in [("Bilodeau, Tyler","Out","G League - Two-Way"),("Brown Jr., Mikel","Questionable","Injury/Illness - Illness"),("Jefferson, Joshua","Out","G League - On Assignment"),("Nelson, Grant","Out","G League - Two-Way"),("Saraf, Ben","Out","G League - On Assignment"),("Traore, Nolan","Probable","Injury/Illness - Right Calf Tightness / Soreness")]:
    add(D14,"08:00 (ET)","BKN@MEM","Brooklyn Nets",p,s,r,"R")
add(D14,"08:00 (ET)","BKN@MEM","Memphis Grizzlies","","NOT YET SUBMITTED","","R")
add(D14,"08:00 (ET)","CHI@MIN","Chicago Bulls","","NOT YET SUBMITTED","","R")
add(D14,"08:00 (ET)","CHI@MIN","Minnesota Timberwolves","","NOT YET SUBMITTED","","R")
for p,s,r in [("Duren, Jalen","Out","Injury/Illness - Right Hamstring Strain"),("Harkless, Elijah","Questionable","G League - Two-Way"),("Joe, Isaiah","Out","Injury/Illness - Right Hip Contusion"),("Jones, Isaac","Questionable","G League - Two-Way"),("Lanier, Chaz","Out","G League - On Assignment"),("Okorie, Ebuka","Out","G League - On Assignment"),("Onyenso, Ugonna","Out","G League - Two-Way")]:
    add(D14,"08:00 (ET)","DET@MIA","Detroit Pistons",p,s,r,"R")
add(D14,"08:00 (ET)","DET@MIA","Miami Heat","","NOT YET SUBMITTED","","R")
# Schedule-linked matchups (S rows): fill matchup from official schedule pairing, verified against the schedule PDF
sched_match={"Chicago Bulls":"ATL@CHI","Miami Heat":"CLE@MIA","San Antonio Spurs":"GSW@SAS","LA Clippers":"OKC@LAC"}
for r in rows:
    if r["attribution"]=="S" and r["team"]=="Cleveland Cavaliers": r["matchup"]="DAL@CLE"
    elif r["attribution"]=="S" and r["matchup"]=="" and r["team"] in sched_match: r["matchup"]=sched_match[r["team"]]
for i,r in enumerate(rows,1):
    r["id"]=f"INJ-{i:03d}"
    r["report_stamp"]="11/13/26 05:00 PM"
    r["report_source"]=PDF
    r["status_as_printed"]=r.pop("status")
    if r["status_as_printed"]=="NOT YET SUBMITTED": r["flag"]="Team-level row printed as NOT YET SUBMITTED (no player statuses yet in this report)"
    elif r["attribution"]=="U": r["flag"]="Team/matchup cell not extracted from PDF text — left blank; verify in PDF"
    elif r["attribution"]=="S": r["flag"]="Team printed; matchup linked via official schedule pairing (confirm in PDF)"
    elif r["attribution"]=="T": r["flag"]="Team status 'NOT YET SUBMITTED' as printed"
    else: r["flag"]=""
    if r["matchup"] and not r["game_time_et"] and r["status_as_printed"]!="NOT YET SUBMITTED": r["flag"] = (r["flag"]+"; " if r["flag"] else "")+"Game time not printed in this row"
    r["ids_note"]=""
json.dump(rows,open("data/injuries.json","w"),indent=1,ensure_ascii=False)
from collections import Counter
print(len(rows), Counter(r["attribution"] for r in rows), Counter(r["game_date"] for r in rows))
