import json

def update_db(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for g in data:
        if str(g.get('thread_id')) == '844':
            g['winning_faction'] = 'Town'
            box = g.get('box_score', {})
            box['winning_faction'] = 'Town'
            box['mvp'] = {
                'player': 'ZichtOpZee & Surviving Townies',
                'rationale': 'Navigated two warring Mafia families and eliminated both syndicates, with ZichtOpZee converted to Town at endgame to cement the Town victory.'
            }
            if 'notable_moments' in box:
                note = "Moderator [TI] arsbury officially announced 'Congratulations survivors! Townies have won!' converting the surviving Serial Killer (ZichtOpZee) to Town."
                if note not in box['notable_moments']:
                    box['notable_moments'].append(note)
            
            for p in box.get('roster', []):
                p_name = p.get('player')
                if p_name == 'ZichtOpZee':
                    p['role'] = 'Serial Killer (Converted to Town)'
                    p['alignment'] = 'Town'
                    p['survived'] = True
                    p['is_winner'] = True
                elif p.get('alignment') == 'Town':
                    p['is_winner'] = True
                elif p.get('alignment') == 'Mafia':
                    p['is_winner'] = False
            g['box_score'] = box
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f'Updated {path}')

update_db('Website/database/historic_forum.json')
update_db('data/database/historic_forum.json')

summary_text = """### Chapter 1: The Gathering in Amaroni
The city of Amaroni was a powder keg, and the fuse had just been lit. Moderator [TI] arsbury announced an experimental structure: two rival Mafia families, the Gagliano and the Morales, were to wage a silent, bloody war against the town and each other. The atmosphere was thick with paranoia. Players like Iluvatar and Wild Flower Soul engaged in banter that masked the cold, calculating nature of the game, while the late entry of 24 players—one over the planned capacity—ensured that the streets were crowded with potential victims and hidden executioners.

### Chapter 2: The First Blood
The night was not kind to the citizens of Amaroni. As the shadows stretched, the first casualties fell. EDN, a Gagliano mobster, was struck down by the Serial Killer, while Eltara, the Gagliano Con Artist, met his end at the hands of the Morales family. The town awoke to the realization that their peace had been shattered. Accusations flew with reckless abandon. Impreza became the primary target for the first lynch, condemned by the collective suspicion of those who saw his lack of IRC activity as a mark of guilt.

### Chapter 3: Web of Deceit
The game devolved into a chaotic struggle for survival. Decimus of the Morales family attempted to keep the town in line with crude commands, while Iluvatar attempted to play detective, theorizing on voting patterns and the "classic moves" of hidden mobsters. However, the carnage continued unabated. The Serial Killer proved to be a relentless force, picking off hitmen and townies alike, while the Morales family tightened their grip by assassinating the Judge, Lynns. With the Judge dead, the power of the gallows became a vacuum, leaving the town vulnerable to the unchecked influence of the Mafia families.

### Chapter 4: The Final Stand & Town Victory
As the bodies piled up, the duality of the threat became clear. The Gagliano Janitor, Genesis, was lynched by an angry mob, and the Morales Godfather, Gratitude, eventually met the same fate as the town finally began to pierce the veil of the families. In the end, both competing criminal syndicates were utterly dismantled. In the official endgame announcement, Moderator [TI] arsbury declared: *"Congratulations survivors! The Townies have won the game!"* With all mafia members eliminated, the surviving Serial Killer (ZichtOpZee) was converted to Town alignment, joining the surviving Townies in celebrating a historic Town Victory.
"""

for s_path in ['Website/stories/844_summary.md', 'data/stories/844_summary.md']:
    with open(s_path, 'w', encoding='utf-8') as f:
        f.write(summary_text)
    print(f'Updated {s_path}')

story_addon = """

---

## 🏆 Endgame Resolution & Role Reveals

### Moderator Endgame Announcement
*"Congratulations survivors! The Townies have won the game!"*

With both the Gagliano and Morales Mafia families completely eliminated, Moderator **[TI] arsbury** officially announced the conclusion of IC Mafia 11. The surviving Serial Killer (**ZichtOpZee**) was converted to Town alignment, sealing a celebrated **Town Victory** alongside the surviving townspeople.
"""

for st_path in ['Website/stories/844_story.md', 'data/stories/844_story.md']:
    with open(st_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'Endgame Resolution' not in content:
        content = content.rstrip() + story_addon
        with open(st_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Appended endgame to {st_path}')
