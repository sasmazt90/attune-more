#!/usr/bin/env python3
"""Source of shared/mental/closing-catalog/v1/catalog.json (33 general closing lines x TR/EN/DE with conditions, cues and
false-match examples). Run from anywhere; rewrites the catalog. Any text change needs new recordings and a new manifest."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / 'shared/mental/closing-catalog/v1/catalog.json'
P = []
D_EN = r"(can't|cannot|hard to|struggle to|struggling to|difficult to|unable to|having trouble|hard time|haven't been able to|couldn't)"
D_DE = r'(kann|konnte|könnte)\b[^.]{0,15}\b(nicht|kaum)\b[^.]{0,40}'
def add(n, key, tr, en, de, cond, cues, false=(), kind='concern', change_topic=False, negated_cue=False, subject_only=False, exclude=None):
    P.append({'id': 'C%02d' % n, 'key': key, 'kind': kind, 'text': {'tr': tr, 'en': en, 'de': de}, 'condition': cond,
              'cues': cues, 'falseMatches': [{'language': l, 'user': u, 'why': w} for l, u, w in false],
              'changeIsTopic': change_topic, 'negatedCue': negated_cue, 'subjectOnly': subject_only, 'objectOk': n in (6, 7, 19, 28), 'exclude': exclude or {}})
NEG_TR_IN = 'değil|yok'
add(1, 'pressure', 'Üzerindeki baskıdan söz ettin.', 'You talked about the pressure you are under.', 'Sie sprachen über den Druck, der auf Ihnen lastet.',
    'The user says they themselves are under pressure (work, family, time, in general). Not blood pressure, not someone else being pressured.',
    {'tr': [r'\bbaskı\w*', r'\bsıkıştır\w*'], 'en': [r'\b(?<!blood )pressure\w*', r'\bpressured\b'], 'de': [r'\b(?!blut)\w*druck\b', r'\bunter druck\b']},
    [('tr', 'Tansiyonum yüksek, kan basıncım değişiyor.', 'blood pressure is a health value, not pressure on the person'),
     ('en', 'My sister is under a lot of pressure at work.', 'third person')])
add(2, 'stress', 'Stres altında olduğundan söz ettin.', 'You talked about being under stress.', 'Sie sprachen darüber, dass Sie unter Stress stehen.',
    'The user says they are stressed now. Not when negated ("I am not stressed"), not about someone else, not when it is over ("I used to be stressed, not any more").',
    {'tr': [r'\bstres\w*', r'\bgergin\w*'], 'en': [r'\bstress\w*', r'\btense\b'], 'de': [r'\bstress\w*', r'\bgestresst\b', r'\bangespannt\b']},
    [('tr', 'Stresli değilim.', 'negated'), ('tr', 'Arkadaşım çok stresli.', 'third person'), ('tr', 'Eskiden stresliydim, artık değilim.', 'past, no longer'),
     ('en', 'I am not stressed.', 'negated'), ('en', 'My friend is stressed.', 'third person'), ('en', 'I used to be stressed, but not anymore.', 'past, no longer'),
     ('de', 'Ich bin nicht gestresst.', 'negated'), ('de', 'Mein Freund ist gestresst.', 'third person'), ('de', 'Früher war ich gestresst, jetzt nicht mehr.', 'past, no longer')])
add(3, 'self-expression', 'Kendini ifade etmekte zorlandığından bahsettin.', 'You talked about finding it hard to express yourself.', 'Sie sprachen darüber, dass es Ihnen schwerfällt, sich auszudrücken.',
    'The user says they find it hard to put their own thoughts or feelings into words. Never inferred from others not listening ("my mother does not listen to me" is C07).',
    {'tr': [r'\b(kendimi|düşüncelerimi|duygularımı|hislerimi|derdimi)\s+(ifade|anlat)\w*\s+(edemi\w*|edem\w*|zorlan\w*)', r'\banlatamıyorum\b', r'\bifade edemiyorum\b', r'\bne hissettiğimi (söyleyemiyorum|anlatamıyorum)'],
     'en': [r'\b' + D_EN + r'\b[^.]{0,25}\bexpress (myself|my feelings|what i feel)', r'\bput (it|my feelings|things) into words\b'],
     'de': [r'(schwer|kann\w* nicht|schaffe\w* nicht)[^.]{0,30}(mich auszudrücken|ausdrücken|in worte (zu )?fassen)']},
    [('tr', 'Annem beni hiç dinlemiyor.', 'others not listening is C07, not self-expression'), ('en', 'My mother never listens to me.', 'C07, not C03')])
add(4, 'rest', 'Yeterince dinlenemediğinden söz ettin.', 'You talked about not getting enough rest.', 'Sie sprachen darüber, dass Sie sich nicht genug erholen können.',
    'The user says they cannot rest or recover enough (dinlenmek / istirahat). Not about being listened to ("sözüm dinlenmiyor" is C07).',
    {'tr': [r'\bdinlenemi\w*', r'\bdinlenemedi\w*', r'\bdinlenmeye (vakit|zaman)\w*\s+(yok|bulamı\w*)', r'\byeterince dinlenmi\w*', r'\bistirahat edemi\w*', r'\bdinlenecek (vakit|zaman)\w*\s+(yok|kalmı\w*)'],
     'en': [r"\b(can't|cannot|don't|never|not)\b[^.]{0,20}\b(rest|recover)\b", r'\bno time to rest\b', r'\bnot (getting|get) enough rest\b'],
     'de': [r'\b(kann|komme)\w*\b[^.]{0,20}\b(nicht|kaum)\b[^.]{0,12}\b(zur ruhe|erholen|ausruhen)', r'\bkeine zeit (zum|zu) (erholen|ausruhen)', r'\bnicht genug (ruhe|erholung)', r'\berhole mich (nicht|kaum)']},
    [('tr', 'Sözüm hiç dinlenmiyor.', 'listening, not rest (C07)'), ('tr', 'Dinlenmek istiyorum.', 'a wish, not a difficulty')], negated_cue=True)
add(5, 'interest', 'Bazı şeylere ilgini kaybettiğini belirttin.', 'You mentioned losing interest in some things.', 'Sie erwähnten, dass Sie an manchen Dingen das Interesse verloren haben.',
    'The user says they lost interest or enjoyment in things they used to like.',
    {'tr': [r'\bilgimi kaybet\w*', r'\bilgim kalmadı', r'\beskisi gibi (keyif|zevk) al(a|ama)\w*', r'\b(isteğim|hevesim) kalmadı'],
     'en': [r'\blost (all )?interest\b', r'\blosing interest\b', r"\bdon't enjoy [^.]{0,30}anymore\b"],
     'de': [r'\binteresse [^.]{0,30}verloren', r'\bkeine lust mehr\b', r'\bmacht mir keinen spaß mehr\b']},
    [('en', 'I have no interest in football.', 'a preference, not a loss')], change_topic=True)
add(6, 'attention', 'Sana yeterince ilgi gösterilmediğinden bahsettin.', 'You talked about not getting enough attention.', 'Sie sprachen darüber, dass Ihnen zu wenig Aufmerksamkeit geschenkt wird.',
    'The user says others do not pay enough attention to them or care about them. The user is the one receiving (or not) attention.',
    {'tr': [r'\b(bana|bize) (yeterince )?(ilgi|önem) (göster|ver)\w*m\w*', r'\b(kimse|kimsenin) (beni|benimle) (umursa|ilgilen)\w*', r'\bbeni umursamıyor\w*', r'\bbenimle ilgilenmiyor\w*'],
     'en': [r"\b(no one|nobody|doesn't|don't|never)\b[^.]{0,20}\b(cares? about me|pays? attention to me|notices? me)", r'\bnot getting (enough )?attention\b', r'\bignores? me\b'],
     'de': [r'\b(niemand|keiner|nicht)\b[^.]{0,20}(kümmert sich um mich|beachtet mich|interessiert sich für mich)', r'\bzu wenig aufmerksamkeit\b', r'\bignoriert mich\b']},
    [('tr', 'Ben anneme yeterince ilgi göstermiyorum.', 'the user is the one not giving attention'), ('en', 'I do not pay attention to my mother.', 'roles reversed')])
add(7, 'not-listened', 'Söylediklerine kulak verilmemesinden söz ettin.', 'You talked about not being listened to.', 'Sie sprachen darüber, dass Ihnen nicht zugehört wird.',
    'The user says others do not listen to them (the user is the one not heard). Not when the user does not listen to someone else; not about resting.',
    {'tr': [r'\b(beni|bizi|söylediklerimi|sözümü|dediklerimi) (hiç |pek |kimse )?(dinlemiyor\w*|dinlemez\w*|dinlemedi\w*)', r'\bsözüm (hiç )?dinlenmiyor', r'\bkulak (vermiyor|asmıyor)\w*', r'\bbeni duymuyor\w*'],
     'en': [r"\b(doesn't|don't|never|won't|no one|nobody)\b[^.]{0,15}\blisten\w* to me\b", r'\bnot (being )?listened to\b', r'\bnobody hears me\b'],
     'de': [r'\b(hört|hören) mir (nie|nicht|kaum)\w* zu\b', r'\bniemand hört mir zu\b', r'\bmir wird nicht zugehört\b']},
    [('tr', 'Ben annemi hiç dinlemiyorum.', 'the user does not listen to someone else'), ('en', 'I never listen to my mother.', 'roles reversed'), ('tr', 'Dinlenemiyorum.', 'rest (C04)')],
    negated_cue=True)
add(8, 'tired', 'Kendini yorgun hissettiğinden söz ettin.', 'You talked about feeling tired.', 'Sie sprachen darüber, dass Sie sich müde fühlen.',
    'The user says they feel tired or exhausted.',
    {'tr': [r'\byorgun\w*', r'\byorul\w*', r'\bbitkin\w*', r'\btüken\w*'], 'en': [r'\btired\b', r'\bexhausted\b', r'\bworn out\b', r'\bwearing me out\b', r'\bdrained\b'], 'de': [r'\bmüde\b', r'\berschöpf\w*', r'\bausgelaugt\b']},
    [('en', 'My father is tired all the time.', 'third person'), ('tr', 'Yorgun değilim.', 'negated')])
add(9, 'sleep', 'Uykuyla ilgili yaşadığın güçlüklerden söz ettin.', 'You talked about difficulties with sleep.', 'Sie sprachen über Ihre Schwierigkeiten mit dem Schlaf.',
    'The user describes their own sleep difficulty (interrupted, too little, cannot fall asleep). Not "my sleep is good", not "I have no sleep problem".',
    {'tr': [r'\buyku\w*\s+(sorun|problem|bölün|kaç|düzensiz|zor|bozul|bozuk)\w*', r'\buyuyam\w*', r'\buykusuz\w*', r'\bgece\w* (sık sık |sürekli )?uyan\w*', r'\buykuya dal(a|ama)\w*', r'\buykumu alamı\w*'],
     'en': [r"\b(can't|cannot|trouble|hard|difficult|struggle)\b[^.]{0,20}\bsleep", r'\bsleep\w*[^.]{0,20}\b(interrupted|bad|poor|broken|disrupted|disturbed)\b', r'\binsomnia\b', r'\bwake up[^.]{0,15}\b(often|at night|several)', r'\bsleepless\b', r'\bsleep problems?\b'],
     'de': [r'\b' + D_DE + r'(ein)?schlafen\b', r'\bschlaf\w*[^.]{0,20}(unterbrochen|gestört)', r'\bschlafprobleme?\b', r'\bschlafstörung\w*', r'\bschlafe\b[^.]{0,12}\bschlecht\b', r'\bwache[^.]{0,15}auf\b']},
    [('tr', 'Uyku sorunum yok.', 'negated'), ('en', 'I sleep well these days.', 'no difficulty')])
add(10, 'focus', 'Odaklanmakta zorlandığından söz ettin.', 'You talked about finding it hard to concentrate.', 'Sie sprachen darüber, dass es Ihnen schwerfällt, sich zu konzentrieren.',
    'The user says they find it hard to concentrate or focus.',
    {'tr': [r'\bodaklanam\w*', r'\bkonsantre ol(a|ama)m\w*', r'\bdikkatimi (toplayam|veremi)\w*', r'\bdikkatim dağıl\w*'],
     'en': [r'\b' + D_EN + r'\b[^.]{0,10}\b(focus|concentrate)', r'\bdistracted\b'],
     'de': [r'\b' + D_DE + r'konzentrieren\b', r'\bkonzentrationsprobleme?\b', r'\bschwer, mich zu konzentrieren', r'\babgelenkt\b']},
    [('en', 'I focus well at work.', 'no difficulty')], negated_cue=True)
add(11, 'worry', 'Seni kaygılandıran konulardan söz ettin.', 'You talked about things that worry you.', 'Sie sprachen über Dinge, die Ihnen Sorgen machen.',
    'The user says something worries them or makes them anxious.',
    {'tr': [r'\bkaygı\w*', r'\bendişe\w*', r'\btedirgin\w*', r'\bhuzursuz\w*'], 'en': [r'\bworr\w*', r'\banxious\b', r'\banxiety\b', r'\bnervous\b'], 'de': [r'\bsorge\w*', r'\bsorgen\b', r'\bangst\b', r'\bängstlich\w*', r'\bnervös\b', r'\bunruhig\b', r'\bbeunruhigt\b']},
    [('de', 'Ich habe keine Angst vor der Prüfung.', 'negated'), ('en', 'My brother is anxious.', 'third person')])
add(12, 'uncertainty', 'Belirsizlikle baş etmekte zorlandığından söz ettin.', 'You talked about finding uncertainty hard to cope with.', 'Sie sprachen darüber, dass Ihnen der Umgang mit Ungewissheit schwerfällt.',
    'The user says not knowing what will happen weighs on them.',
    {'tr': [r'\bbelirsiz\w*', r'\bne olacağını bilme\w*', r'\bne olacağı belli değil'], 'en': [r'\buncertain\w*', r"\bdon't know what (will|is going to) happen", r'\bnot knowing\b'], 'de': [r'\bungewiss\w*', r'\bunsicherheit\b', r'\bweiß nicht, was (kommt|passiert|wird)']},
    [('en', 'I know exactly what will happen next.', 'no uncertainty')])
add(13, 'decisions', 'Karar vermekte zorlandığın konulardan söz ettin.', 'You talked about decisions you find hard to make.', 'Sie sprachen über Entscheidungen, die Ihnen schwerfallen.',
    'The user says they find it hard to decide something.',
    {'tr': [r'\bkarar\w*\s+(ver(e|a)m\w*|vermekte\s+(\w+\s+)?zorlan\w*|veremi\w*)', r'\bkararsız\w*'], 'en': [r'\b' + D_EN + r'\b[^.]{0,10}\b(decide|make (a|the|this) decision)', r'\bindecisive\b', r'\btorn between\b'],
     'de': [r'\b' + D_DE + r'entscheiden\b', r'\bentscheidung\w* (fällt|fallen) mir schwer', r'\bunentschlossen\b']},
    [('en', 'I decided to change jobs.', 'a decision made, no difficulty')], negated_cue=True)
add(14, 'responsibilities', 'Sorumluluklarının seni zorladığından söz ettin.', 'You talked about your responsibilities weighing on you.', 'Sie sprachen darüber, dass Ihre Verantwortung Sie belastet.',
    'The user says their responsibilities strain or overwhelm them. Having many responsibilities alone ("I have a lot of responsibilities") is not enough.',
    {'tr': [r'\bsorumluluk\w*[^.]{0,40}(zorl|bunal|ağır|yetişemi|ezil|fazla geliyor)\w*', r'\b(zorl|bunal|ezil)\w*[^.]{0,40}sorumluluk\w*'],
     'en': [r'\bresponsibilit\w*[^.]{0,40}(overwhelm|too much|weigh|struggl|keep up|crush)\w*', r'\b(overwhelm|struggl)\w*[^.]{0,40}responsibilit\w*'],
     'de': [r'\bverantwortung\w*[^.]{0,40}(überfordert|zu viel|belastet|lastet|erdrückt)', r'\b(überfordert|belastet)[^.]{0,40}verantwortung\w*']},
    [('tr', 'Çok sorumluluğum var.', 'having responsibilities is not being strained by them'), ('en', 'I have a lot of responsibilities.', 'no strain stated')])
add(15, 'expectations', 'Beklentileri karşılamakta zorlandığından söz ettin.', 'You talked about struggling to meet expectations.', 'Sie sprachen darüber, dass es Ihnen schwerfällt, Erwartungen zu erfüllen.',
    'The user says they struggle to meet expectations (their own or others\').',
    {'tr': [r'\bbeklenti\w*[^.]{0,40}(karşılayam|yetişemi|zorlan|yetemi|başaram)\w*'], 'en': [r'\bexpectation\w*[^.]{0,40}(meet|live up|struggl|hard)', r'\b' + D_EN + r'\b[^.]{0,10}\b(meet|live up to)\b[^.]{0,20}expectation'],
     'de': [r'\berwartung\w*[^.]{0,40}(erfüllen|gerecht|schaffe|schwer)']},
    [('en', 'My expectations for the trip are high.', 'no struggle stated')])
add(16, 'me-time', 'Kendine zaman ayırmakta zorlandığından söz ettin.', 'You talked about finding it hard to make time for yourself.', 'Sie sprachen darüber, dass Sie kaum Zeit für sich selbst finden.',
    'The user says they have little or no time for themselves.',
    {'tr': [r'\bkendime (vakit|zaman) (ayıram|bulam|kalmı|yok)\w*', r'\bkendime ayıracak (vakit|zaman)\w*\s+(yok|kalmı\w*)'], 'en': [r"\b(no|not enough|never have|can't find|hard to find|don't have|little) (any )?time for myself\b", r'\bno time for me\b'],
     'de': [r'\b(keine|kaum|wenig) zeit für mich\b', r'\bkomme nicht dazu, etwas für mich']},
    [('en', 'I took time for myself this weekend.', 'no difficulty')], negated_cue=True)
add(17, 'lonely', 'Kendini yalnız hissettiğinden söz ettin.', 'You talked about feeling lonely.', 'Sie sprachen darüber, dass Sie sich einsam fühlen.',
    'The user says they feel lonely. Living alone ("Yalnız yaşıyorum", "I live alone") is not loneliness.',
    {'tr': [r'\byalnız hissed\w*', r'\bkendimi yalnız\w*', r'\byalnızlık\w*', r'\byapayalnız\w*'], 'en': [r'\blonely\b', r'\bloneliness\b', r'\bfeel (so )?alone\b', r'\bisolated\b'], 'de': [r'\beinsam\w*', r'\bfühle mich allein\b']},
    [('tr', 'Yalnız yaşıyorum.', 'living alone is not loneliness'), ('en', 'I live alone.', 'living alone is not loneliness'), ('de', 'Ich wohne allein.', 'living alone is not loneliness')])
add(18, 'missing', 'Özlem duyduğun kişilerden söz ettin.', 'You talked about people you miss.', 'Sie sprachen über Menschen, die Sie vermissen.',
    'The user says they miss people.',
    {'tr': [r'\bözlü(yorum|yoruz)\b', r'\bözledi(m|k)\b', r'\bözlem\w*', r'\bhasret\w*'], 'en': [r"\bi (really |so )?miss(ed)? (my|him|her|them|you|our|home|family|friends)\b", r'\bhomesick\b'], 'de': [r'\bvermisse\b', r'\bsehnsucht\b', r'\bfehlt mir\b', r'\bfehlen mir\b', r'\bheimweh\b']},
    [('en', 'I missed the bus this morning.', 'missing a bus is not missing people'), ('de', 'Die Abende mit meinen Freunden.', 'a fragment; missing is not said')])
add(19, 'misunderstood', 'Anlaşılmadığını hissettiğinden söz ettin.', 'You talked about feeling misunderstood.', 'Sie sprachen darüber, dass Sie sich nicht verstanden fühlen.',
    'The user says others do not understand them.',
    {'tr': [r'\b(kimse )?beni anlamıyor\w*', r'\banlaşılmıyor\w*', r'\banlaşılmadığ\w*'], 'en': [r"\b(nobody|no one|doesn't|don't)\b[^.]{0,15}\bunderstands? me\b", r'\bmisunderstood\b', r'\bnot understood\b'],
     'de': [r'\b(niemand|keiner) versteht mich\b', r'\bversteh\w* mich nicht\b', r'\bmissverstanden\b', r'\bnicht verstanden\b']},
    [('en', 'I do not understand my teacher.', 'the user does not understand someone')], negated_cue=True)
add(20, 'disagreements', 'Yaşadığın anlaşmazlıklardan söz ettin.', 'You talked about disagreements you have had.', 'Sie sprachen über Meinungsverschiedenheiten, die Sie erlebt haben.',
    'The user says they argue or have conflicts with someone (the user is one of the parties).',
    {'tr': [r'\btartış\w*', r'\bkavga\w*', r'\banlaşmazlık\w*', r'\banlaşam\w*'], 'en': [r'\bargu\w*', r'\bfight\w*', r'\bconflict\w*', r'\bdisagree\w*', r'\bfell out\b'], 'de': [r'\bstreit\w*', r'\bgestritten\b', r'\bkonflikt\w*', r'\bmeinungsverschiedenheit\w*']},
    [('tr', 'Annemle babam sürekli kavga ediyor.', 'the user is not a party'), ('en', 'My parents argue a lot.', 'the user is not a party')])
add(21, 'boundaries', 'Sınır koymakta zorlandığın durumlardan söz ettin.', 'You talked about finding it hard to set boundaries.', 'Sie sprachen darüber, dass es Ihnen schwerfällt, Grenzen zu setzen.',
    'The user says they find it hard to say no or set limits.',
    {'tr': [r'\bhayır diyemi\w*', r'\bhayır demekte zorlan\w*', r'\bsınır (koy|çiz)(a|ama)m\w*', r'\bsınır koymakta zorlan\w*'], 'en': [r'\b' + D_EN + r'\b[^.]{0,10}\b(say no|set boundaries|set limits)\b'],
     'de': [r'\b(kann|konnte) nicht nein sagen\b', r'\bschwer, nein zu sagen\b', r'\bnein sagen fällt mir schwer\b', r'\bgrenzen (zu )?setzen[^.]{0,20}(schwer|kann nicht)']},
    [('en', 'I said no to my boss today.', 'a boundary set, no difficulty')], negated_cue=True)
add(22, 'change', 'Değişimlere uyum sağlamakta zorlandığından söz ettin.', 'You talked about finding it hard to adapt to changes.', 'Sie sprachen darüber, dass Ihnen die Anpassung an Veränderungen schwerfällt.',
    'The user says they find it hard to adapt to a change (move, new job, new routine).',
    {'tr': [r'\b(değişim|değişiklik|yeni düzen|taşın)\w*[^.]{0,40}(uyum sağlay(a|ama)m|alışam|zorlan|adapte olam)\w*', r'\balışamıyorum\b', r'\balışamadım\b'],
     'en': [r'\b(hard|difficult|struggl\w*|' + D_EN[1:-1] + r')\b[^.]{0,10}\b(adjust|adapt|get used)', r'\bthe change is (wearing me out|hard)\b'],
     'de': [r'\b(schwer|kann\b[^.]{0,10}\bnicht|schaffe es nicht)[^.]{0,30}(gewöhnen|anpassen|umstellen)', r'\bgewöhne mich (nicht|kaum)\b', r'\bdie veränderung erschöpft mich\b']},
    [('en', 'The change went smoothly.', 'no difficulty')], negated_cue=True)
add(23, 'sad', 'Seni üzen konulardan söz ettin.', 'You talked about things that make you sad.', 'Sie sprachen über Dinge, die Sie traurig machen.',
    'The user says something makes them sad or upset.',
    {'tr': [r'\büzgün\w*', r'\büzül\w*', r'\büzüyor\w*', r'\bmutsuz\w*'], 'en': [r'\bsad\b', r'\bsadness\b', r'\bupset\w*', r'\bunhappy\b', r'\bfeel(ing)? down\b'], 'de': [r'\btraurig\w*', r'\bbedrückt\b', r'\bniedergeschlagen\b', r'\bunglücklich\b']},
    [('en', 'My friend is sad.', 'third person')])
add(24, 'disappointment', 'Yaşadığın hayal kırıklığından söz ettin.', 'You talked about a disappointment you experienced.', 'Sie sprachen über eine Enttäuschung, die Sie erlebt haben.',
    'The user says they were disappointed.',
    {'tr': [r'\bhayal kırıklığı\w*'], 'en': [r'\bdisappoint\w*', r'\blet down\b'], 'de': [r'\benttäusch\w*']},
    [('en', 'I was not disappointed at all.', 'negated')])
add(25, 'anger', 'Seni öfkelendiren durumlardan söz ettin.', 'You talked about situations that make you angry.', 'Sie sprachen über Situationen, die Sie wütend machen.',
    'The user says something makes them angry.',
    {'tr': [r'\bsinirlen\w*', r'\bsinirim\w*', r'\böfke\w*', r'\bkızgın\w*', r'\bkızıyorum\b', r'\bkızdım\b'], 'en': [r'\bangry\b', r'\banger\b', r'\bfurious\b', r'\bmad at\b', r'\bannoyed\b', r'\bfrustrat\w*'], 'de': [r'\bwütend\b', r'\bwut\b', r'\bärger\w*', r'\bsauer\b', r'\bzornig\b']},
    [('tr', 'Kız kardeşim bugün geldi.', '"kız" is not anger')])
add(26, 'self-trust', 'Kendine güvenmekte zorlandığından söz ettin.', 'You talked about finding it hard to trust yourself.', 'Sie sprachen darüber, dass es Ihnen schwerfällt, sich selbst zu vertrauen.',
    'The user says they doubt themselves or lack self-confidence.',
    {'tr': [r'\bkendime güven(em|emi|im yok|miyorum)\w*', r'\bözgüven\w*\s+(yok|düşük|eksik)\w*', r'\bkendimden şüphe\w*'], 'en': [r"\b(don't|can't|hard to) trust myself\b", r'\bself-doubt\b', r'\bdoubt myself\b', r'\b(no|lack of|low) (self-)?confidence\b', r'\blow self-esteem\b'],
     'de': [r'\b(vertraue|traue) mir (selbst )?nicht\b', r'\bzweifle an mir\b', r'\bselbstzweifel\b', r'\b(kein|wenig) selbstvertrauen\b']},
    [('en', 'I trust myself with this decision.', 'no doubt')], negated_cue=True)
add(27, 'helps', 'Sana iyi gelen şeylerden söz ettin.', 'You talked about things that do you good.', 'Sie sprachen über Dinge, die Ihnen guttun.',
    'The user says something helps them or does them good.',
    {'tr': [r'\biyi (geliyor|geldi|gelir)\b', r'\brahatlatıyor\b', r'\bsakinleştiriyor\b', r'\bişe yarıyor\b', r'\bkeyif alıyorum\b'], 'en': [r'\bhelps? (me|a bit|a little|somewhat)\b', r'\bdoes me good\b', r'\bcalms me( down)?\b', r'\bmakes? me feel better\b', r'\brelaxes me\b'],
     'de': [r'\btut mir gut\b', r'\b(hilft|helfen) (mir|etwas)\b', r'\bberuhigt mich\b', r'\bentspannt mich\b']},
    [('en', 'Nothing helps me.', 'negated')], kind='positive')
add(28, 'support', 'Çevrenden gördüğün destekten söz ettin.', 'You talked about the support you get from people around you.', 'Sie sprachen über die Unterstützung aus Ihrem Umfeld.',
    'The user says people around them support them.',
    {'tr': [r'\b(bana )?destek (oluyor|veriyor|oldu|aldım|alıyorum)\w*', r'\byanımda\b'], 'en': [r'\bsupports? me\b', r'\bsupported me\b', r'\bsupportive\b', r'\bthere for me\b'],
     'de': [r'\bunterstütz\w* mich\b', r'\bunterstützung (von|durch|meiner|meines)\b', r'\b(ist|sind)\b[^.]{0,15}\bfür mich da\b']},
    [('en', 'Nobody supports me.', 'negated')], kind='positive')
add(29, 'relief', 'Kendini rahatlamış hissettiğinden söz ettin.', 'You talked about feeling relieved.', 'Sie sprachen darüber, dass Sie sich erleichtert fühlen.',
    'The user says they feel relieved or lighter now.',
    {'tr': [r'\brahatladım\b', r'\brahatlamış\w*', r'\bferahladım\b', r'\biçim rahatladı\b', r'\bhafifledim\b'], 'en': [r'\brelieved\b', r'\brelief\b', r'\bfeel (lighter|calmer)\b'], 'de': [r'\berleichter\w*', r'\bfühle mich leichter\b']},
    [('en', 'I do not feel relieved.', 'negated')], kind='positive', change_topic=True)
add(30, 'happy', 'Seni mutlu eden gelişmelerden söz ettin.', 'You talked about developments that make you happy.', 'Sie sprachen über Entwicklungen, die Sie glücklich machen.',
    'The user says something made them happy.',
    {'tr': [r'\bmutlu\w*', r'\bsevindim\b', r'\bsevindir\w*', r'\bgüzel (bir )?(gelişme|haber)'], 'en': [r'\bhappy\b', r'\bglad\b', r'\bdelighted\b', r'\bgood news\b'], 'de': [r'\bglücklich\b', r'\bfreue mich\b', r'\bfreut mich\b', r'\bgute nachricht\w*']},
    [('tr', 'Mutlu değilim.', 'negated')], kind='positive')
add(31, 'hope', 'Geleceğe ilişkin umutlarından söz ettin.', 'You talked about your hopes for the future.', 'Sie sprachen über Ihre Hoffnungen für die Zukunft.',
    'The user expresses hope about what is coming.',
    {'tr': [r'\bumut\w*', r'\bumuyorum\b'], 'en': [r'\bhope\w*', r'\blooking forward\b', r'\boptimistic\b'], 'de': [r'\bhoffe\b', r'\bhoffnung\w*', r'\bzuversichtlich\b', r'\bfreue mich auf\b']},
    [('en', 'I have no hope.', 'negated')], kind='positive')
add(32, 'goals', 'Ulaşmak istediğin hedeflerden söz ettin.', 'You talked about goals you want to reach.', 'Sie sprachen über Ziele, die Sie erreichen möchten.',
    'The user names something they want to achieve or plan to do.',
    {'tr': [r'\bhedef\w*', r'\bamacım\b', r'\b(ulaşmak|başarmak) istiyorum\b', r'\bçalışacağım\b', r'\bplanlıyorum\b'], 'en': [r'\bgoals?\b', r'\baim to\b', r'\bplan to\b', r'\bi (will|\'ll) try to\b'], 'de': [r'\bziel\w*', r'\bmöchte [^.]{0,20}erreichen\b', r'\bversuche ich\b', r'\bhabe mir vorgenommen\b']},
    [('en', 'I have no goals right now.', 'negated'), ('en', 'My boss has goals for me.', 'someone else\'s goal')], kind='positive', subject_only=True)
add(33, 'proud', 'Kendinle gurur duyduğun bir deneyimden söz ettin.', 'You talked about an experience you are proud of.', 'Sie sprachen über eine Erfahrung, auf die Sie stolz sind.',
    'The user says they are proud of something they did.',
    {'tr': [r'\bgurur (duy|duyuyorum|duydum)\w*', r'\bgururlu\w*', r'\bbaşardım\b'], 'en': [r'\bproud\b', r'\bi managed to\b', r'\bi achieved\b'], 'de': [r'\bstolz\b', r'\bhabe es geschafft\b']},
    [('en', 'My sister is proud of me.', 'someone else is proud'), ('tr', 'Kız kardeşim benimle gurur duyuyor.', 'someone else is proud'), ('en', 'I am proud of my brother.', 'proud of someone else, not of oneself')], kind='positive', subject_only=True,
    exclude={'tr': [r'\b(onunla|onlarla|seninle|sizinle|(?!kendim)\w+(ım|im|um|üm)(la|le)) gurur'], 'en': [r'\bproud of (him|her|them|you|my (?!self)\w+|his|their|our)'], 'de': [r'\bstolz auf (ihn|sie|dich|euch|mein\w* (?!selbst)\w+|unser\w*)']})
out = {'schema': 'attune-closing-catalog-v1', 'version': '1.0.0', 'description': 'Generic spoken closing lines selected by what the user said. The written summary stays personal; only one of these lines is spoken after C. Each line has a usage condition; the server checks the provider\'s choice against the user\'s own words (cues, negation, person, time, later corrections) and speaks nothing when no reliable match remains.',
       'address': {'tr': 'sen', 'en': 'you', 'de': 'Sie'}, 'limits': {'maxWords': 12, 'maxCharacters': 100}, 'patterns': P}
for p in P:
    for l, t in p['text'].items():
        assert len(t) <= 100 and len(t.split()) <= 12, (p['id'], l, t, len(t), len(t.split()))
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), 'utf-8')
print(len(P), max(len(t) for p in P for t in p['text'].values()), max(len(t.split()) for p in P for t in p['text'].values()))
