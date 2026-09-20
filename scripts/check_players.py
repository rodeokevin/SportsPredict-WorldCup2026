import json
d = json.load(open('data/player_history.json', encoding='utf-8'))
players = [
    'Lamine Yamal', 'Ruben Vargas', 'Nestory Irankunda', 'Antoine Semenyo',
    'Bernardo Silva', 'Marcel Sabitzer', 'Breel Embolo', 'Amine Gouiri', 'Riyad Mahrez',
    'Lautaro Martinez', 'Julian Alvarez', 'Luis Diaz', 'James Rodriguez', 'Jordan Ayew',
    'Luka Modric', 'Cristiano Ronaldo', 'Lionel Messi',
]
for p in players:
    found = d.get(p)
    key = p
    if not found:
        for k, v in d.items():
            if p.lower() in k.lower() or k.lower() in p.lower():
                found = v
                key = k
                break
    if found:
        sot_rate = round(found['shots_on_target'] / max(found['matches'], 1), 2)
        print(key.ljust(35), 'm='+str(found['matches']).rjust(3), 'g='+str(found['goals']).rjust(3),
              'a='+str(found['assists']).rjust(3), 'sot='+str(found['shots_on_target']).rjust(4),
              'sot/m='+str(sot_rate))
    else:
        print(p.ljust(35), 'NOT FOUND')
