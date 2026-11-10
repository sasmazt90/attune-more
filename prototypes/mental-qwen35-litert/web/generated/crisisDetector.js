// ../../../shared/localization/urgent-safety.json
var urgent_safety_default = {
  de: ["\\b(?:ich f\xFChle mich(?: gerade)? nicht sicher|ich bin(?: gerade)? nicht sicher|ich bin in gefahr)\\b", "\\b(?:brauche|ben\xF6tige) (?:dringend|sofort|jetzt) hilfe\\b"],
  en: ["\\b(?:i am not safe|i'm not safe|i do not feel safe|i don't feel safe|i am in danger)\\b", "\\b(?:i need|i require|and need) (?:urgent|immediate) help\\b"],
  tr: ["(?:g\xFCvende de\u011Filim|kendimi g\xFCvende hissetmiyorum|tehlikedeyim)", "(?:acil yard\u0131ma ihtiyac\u0131m var|acil yard\u0131m istiyorum|hemen yard\u0131m istiyorum|acilen yard\u0131m istiyorum)"]
};

// ../../../shared/localization/english-crisis.json
var english_crisis_default = {
  legacyKeywords: [
    "suicide",
    "suicidal",
    "kill myself",
    "hurt myself",
    "end my life",
    "want to die",
    "don't want to live",
    "do not want to live"
  ],
  signal: "\\b(?:suicide|suicidal|kill myself|hurt myself|end my life|want to die|(?:don't|do not|never|no longer) want to live|wish(?:ed)? i (?:were|was) dead|rather (?:not )?be dead)\\b",
  selfDirected: "\\b(?:kill myself|hurt myself|end my life|want to die|(?:don't|do not|never|no longer) want to live|i wish i (?:were|was) dead|i(?:'d| would) rather be dead)\\b",
  currentState: "\\b(?:i(?: am|'m| feel| have been feeling) (?:actively |currently |still )?suicidal|i (?:have|keep having|am having) (?:suicidal (?:thoughts|feelings)|thoughts (?:of|about) suicide)|i (?:have|made|am making) (?:(?:a|my) )?suicide (?:plans?|notes?)|i have (?:a|my) plan for suicide|i (?:wrote|am writing|have written) (?:a|my) suicide note|(?:feeling|actively|currently) suicidal|(?:commit|attempt|considering|contemplating|planning|thinking (?:of|about)) (?:my |a )?suicide|suicide (?:is|feels like) (?:my|the) (?:only|best) (?:option|way out)|(?:suicide|suicidal) (?:tonight|now|today)|my suicide (?:plans?|notes?)|i (?:finished|completed|prepared|have prepared|have finished|have completed) my suicide (?:plans?|notes?)|i(?: am|'m) (?:experiencing|struggling with|dealing with) suicidal (?:thoughts|feelings|urges))\\b",
  reassurance: [
    "\\bi (?:don't|do not|never|no longer) (?:want|intend|plan) to (?:die|kill myself|hurt myself|end my life)\\b",
    "\\bi(?: am|'m| feel) (?:not|no longer) (?:currently |actively |feeling )?suicidal\\b",
    "\\bi(?: am|'m) currently not suicidal\\b",
    "\\bi (?:don't|do not|never) feel suicidal(?: anymore| any longer)?\\b",
    "\\bi(?: am|'m) not (?:going|planning|trying|intending) to (?:(?:kill|hurt) myself|commit suicide)\\b",
    "\\bi (?:will not|won't|would not|wouldn't) (?:(?:kill|hurt) myself|commit suicide|end my life)\\b",
    "\\bi(?: am|'m) (?:not|no longer) (?:currently |seriously |actively )?(?:planning|considering|contemplating|thinking (?:of|about)) (?:my |a )?suicide\\b",
    "\\bmy suicide (?:plans?|notes?) (?:is|are) (?:no longer (?:active|relevant)|abandoned|cancelled|canceled)\\b",
    "\\bmy suicide (?:plans?|notes?) (?:does not|doesn't) exist\\b",
    "\\bi (?:have no|do not have|don't have|no longer have|am not having) (?:any )?thoughts (?:of|about) suicide\\b",
    "\\bi(?: am|'m) (?:not|no longer) (?:experiencing|struggling with|dealing with) suicidal (?:thoughts|feelings|urges)\\b",
    "\\bi (?:don't|do not|never|no longer) wish i (?:were|was) dead\\b",
    "\\bi(?:(?: would not| wouldn't) rather be dead|(?:'d| would) rather not be dead)\\b"
  ],
  historical: [
    "\\bi used to (?:feel|be) suicidal\\b",
    "\\bi used to (?:want to die|want to end my life|think about suicide)\\b",
    "\\bmy suicide (?:plans?|notes?) (?:(?:is|are) from (?:years|months) ago|(?:was|were) abandoned (?:years|months) ago)\\b",
    "\\b(?:i found )?my suicide (?:plans?|notes?) from (?:years|months) ago\\b",
    "\\bi used to have thoughts (?:of|about) suicide\\b",
    "\\bi used to (?:experience|struggle with|deal with) suicidal (?:thoughts|feelings|urges)\\b",
    "\\bi used to have (?:my )?suicide (?:plans?|notes?)\\b",
    "\\bi (?:used to wish|wished) i (?:were|was) dead\\b",
    "\\bi (?:used to (?:think|feel)|thought|felt)(?: that)? i(?:'d| would) rather be dead\\b",
    `\\bi used to (?:say|think|feel)(?: that)? ["\u201C'\u2018]?(?:i wish i (?:were|was) dead|i(?:'d| would) rather be dead)\\b["\u201D']?`
  ],
  uncertain: [
    "\\bi(?: am|'m) not sure (?:if|whether) i(?: am|'m| feel) suicidal\\b",
    "\\bi (?:don't|do not) (?:know|think) (?:if |whether |that )?i(?: am|'m| feel) suicidal\\b",
    "\\bi (?:don't|do not) know what (?:suicide|suicidal) means\\b",
    "\\bi (?:don't|do not) (?:think|believe) (?:that )?suicide (?:is|feels like) (?:my|the) (?:only|best) (?:option|way out)\\b",
    '\\b(?:the (?:title|phrase)|a story called) ["\\u201c]?my suicide (?:plans?|notes?)["\\u201d]?',
    "\\bi(?: am|'m) not sure (?:if|whether) i have thoughts (?:of|about) suicide\\b",
    `\\b(?:(?:he|she|they|(?:my|a|the) (?:friend|partner|brother|sister|character|narrator)) (?:said|says|told me|wrote|writes|thought|thinks)|i (?:read|heard|am quoting|was quoting|never said|did not say|didn't say)|the (?:phrase|quote|sentence|title)|what does|the meaning of)[:,]?\\s+["\u201C'\u2018]?(?:i wish i (?:were|was) dead|i(?:'d| would) rather be dead)\\b["\u201D']?`,
    `^["\u201C'\u2018](?:i wish i (?:were|was) dead|i(?:'d| would) rather be dead)[.!?]?["\u201D'][.!?]?$`,
    "\\bi (?:don't|do not|no longer) (?:think|believe) (?:that )?(?:i wish i (?:were|was) dead|i(?:'d| would) rather be dead)\\b",
    `["\u201C'\u2018](?:i wish i (?:were|was) dead|i(?:'d| would) rather be dead)[.!?]?["\u201D'] (?:is|was|appears|appeared|comes|came) (?:(?:just|only) )?(?:(?:a|the) (?:quote|quotation|line|sentence) )?(?:in|from) (?:a|the) (?:book|movie|film|novel|story|article|song|poem|script)\\b`
  ],
  continuedRisk: "\\b(?:but|and) (?:sometimes )?(?:i )?(?:still (?:do|am|feel that way)|feel that way (?:again|now))\\b",
  conditional: "\\b(?:unless|until|if|yet|not sure)\\b"
};

// ../../../shared/localization/german-crisis.json
var german_crisis_default = {
  legacyKeywords: [
    "selbstmord",
    "suizid",
    "mich umbringen",
    "mir etwas antun",
    "mir selbst schaden",
    "nicht mehr leben",
    "sterben will",
    "will sterben"
  ],
  signal: "\\b(?:selbstmord(?:gedanken|plan|pl\xE4ne|plaene)?|suizid(?:al(?:e|en|er|es|em)?|gedanken|plan|pl\xE4ne|plaene)?|mich (?:nicht )?(?:umbringen|umzubringen)|mir (?:etwas|selbst) (?:antun|antue|schaden)|nicht mehr leben|sterben (?:will|m\xF6chte)|(?:will|m\xF6chte) (?:nicht (?:mehr )?)?sterben|(?:will|m\xF6chte) nicht (?:mehr )?leben|ich bringe mich(?: nicht(?: mehr)?)?(?: (?:jetzt|gleich|heute|bald))? um|ich (?:tue|tu) mir (?:etwas|was|selbst etwas|nichts(?: mehr)?)(?: nicht(?: mehr)?)?(?: (?:jetzt|gleich|heute|bald))? an|(?:(?:ich (?:w\xE4re|waere)(?: (?:jetzt|gerade|einfach))? (?:lieber|am liebsten|gerne?) tot|(?:lieber|am liebsten|gerne?) (?:w\xE4re|waere) ich(?: (?:jetzt|gerade))? tot|ich (?:w\xFCnschte|wuenschte|w\xFCnsche|wuensche)(?: mir)?(?:, ?| )(?:ich (?:w\xE4re|waere)(?: (?:lieber|am liebsten|gerne?))? tot|dass ich(?: (?:lieber|am liebsten|gerne?))? tot (?:w\xE4re|waere)|(?:lieber )?tot zu sein)|ich (?:will|m\xF6chte|moechte|(?:w\xFCrde|wuerde) (?:lieber|am liebsten|gerne?))(?: lieber)? tot sein)|(?:lieber|am liebsten|gerne?) (?:nicht(?: mehr)? )?tot|(?:w\xE4re|waere) (?:nicht(?: mehr)? )?tot|(?:w\xE4re|waere) ich (?:nicht(?: mehr)? )?tot|tot (?:zu )?sein|tot (?:w\xE4re|waere)))\\b",
  selfDirected: "\\b(?:mich (?:umbringen|umzubringen)|mir (?:etwas|selbst) (?:antun|antue|schaden)|nicht mehr leben|sterben (?:will|m\xF6chte)|(?:will|m\xF6chte) sterben|(?:will|m\xF6chte) nicht (?:mehr )?leben|ich bringe mich(?: (?:jetzt|gleich|heute|bald))? um|ich (?:tue|tu) mir (?:etwas|was|selbst etwas)(?: (?:jetzt|gleich|heute|bald))? an|(?:ich (?:w\xE4re|waere)(?: (?:jetzt|gerade|einfach))? (?:lieber|am liebsten|gerne?) tot|(?:lieber|am liebsten|gerne?) (?:w\xE4re|waere) ich(?: (?:jetzt|gerade))? tot|ich (?:w\xFCnschte|wuenschte|w\xFCnsche|wuensche)(?: mir)?(?:, ?| )(?:ich (?:w\xE4re|waere)(?: (?:lieber|am liebsten|gerne?))? tot|dass ich(?: (?:lieber|am liebsten|gerne?))? tot (?:w\xE4re|waere)|(?:lieber )?tot zu sein)|ich (?:will|m\xF6chte|moechte|(?:w\xFCrde|wuerde) (?:lieber|am liebsten|gerne?))(?: lieber)? tot sein))\\b",
  currentState: "\\b(?:ich (?:bin|f\xFChle mich)(?: akut|aktuell|gerade|noch)? suizidal|ich habe (?:einen )?(?:(?:suizid|selbstmord)(?:plan|pl\xE4ne|plaene|gedanken))|ich (?:plane|erw\xE4ge|denke an) (?:einen )?(?:selbstmord|suizid)|ich (?:will|m\xF6chte|werde) (?:einen )?(?:selbstmord|suizid) (?:begehen|ver\xFCben)|ich denke \xFCber (?:selbstmord|suizid) nach|ich habe einen plan f\xFCr (?:selbstmord|suizid)|mein(?:e|en|er|em|es)? (?:suizid|selbstmord)(?:plan|pl\xE4ne|plaene)|ich habe meinen (?:suizid|selbstmord)(?:plan|pl\xE4ne|plaene) (?:fertiggestellt|vorbereitet)|ich habe (?:akute |aktuelle )?suizidal(?:e|en) gedanken|ich habe gedanken an (?:selbstmord|suizid))\\b",
  reassurance: [
    "\\bich (?:bin|f\xFChle mich)(?: aktuell|gerade)? (?:nicht|nicht mehr) suizidal\\b",
    "\\bich (?:will|m\xF6chte) nicht (?:mehr )?sterben\\b",
    "\\bich (?:will|m\xF6chte|werde) mich nicht (?:umbringen|umzubringen)\\b",
    "\\bich denke nicht an (?:selbstmord|suizid)\\b",
    "\\bich habe nicht vor,? mich umzubringen\\b",
    "\\bich (?:will|m\xF6chte|werde) (?:keinen (?:selbstmord|suizid) (?:begehen|ver\xFCben)|(?:selbstmord|suizid) nicht (?:begehen|ver\xFCben))\\b",
    "\\bich denke nicht \xFCber (?:selbstmord|suizid) nach",
    "\\bmein(?:e|en|er|em|es)? (?:suizid|selbstmord)(?:plan|pl\xE4ne|plaene) (?:ist|sind) (?:nicht mehr aktiv|aufgegeben|abgebrochen)\\b",
    "\\bmein(?:e|en|er|em|es)? (?:suizid|selbstmord)(?:plan|pl\xE4ne|plaene) existier(?:t|en) nicht\\b",
    "\\bich habe (?:keine|nicht mehr|keine aktuellen) (?:suizid|selbstmord)gedanken(?: mehr)?\\b",
    "\\bich habe (?:keine(?: aktuellen)?|nicht mehr) (?:suizidal(?:e|en) gedanken|gedanken an (?:selbstmord|suizid))(?: mehr)?\\b",
    "\\bich bringe mich nicht(?: mehr)?(?: (?:jetzt|gleich|heute|bald))? um\\b",
    "\\bich (?:tue|tu) mir (?:(?:etwas|was|selbst etwas) nicht(?: mehr)?|nichts(?: mehr)?)(?: (?:jetzt|gleich|heute|bald))? an\\b",
    "\\bich (?:w\xE4re|waere)(?: (?:jetzt|gerade|einfach))? (?:(?:nicht(?: mehr)?|nie) (?:lieber|am liebsten|gerne?)|(?:lieber|am liebsten|gerne?) (?:nicht(?: mehr)?|nie)) tot\\b",
    "\\b(?:lieber|am liebsten|gerne?) (?:w\xE4re|waere) ich (?:nicht(?: mehr)?|nie) tot\\b",
    "\\bich (?:w\xFCnschte|wuenschte|w\xFCnsche|wuensche)(?: mir)? (?:nicht(?: mehr)?|nie)(?:, ?| )(?:ich (?:w\xE4re|waere)(?: (?:lieber|am liebsten|gerne?))? tot|dass ich(?: (?:lieber|am liebsten|gerne?))? tot (?:w\xE4re|waere)|(?:lieber )?tot zu sein)\\b",
    "\\bich (?:w\xFCnschte|wuenschte|w\xFCnsche|wuensche)(?: mir)?(?:, ?| )(?:ich (?:w\xE4re|waere)(?: (?:lieber|am liebsten|gerne?))? nicht tot|dass ich nicht tot (?:w\xE4re|waere)|nicht tot zu sein)\\b",
    "\\bich (?:(?:will|m\xF6chte|moechte) (?:nicht(?: mehr)?|nie)(?: lieber)?|(?:w\xFCrde|wuerde) (?:(?:nicht|nie) (?:lieber|am liebsten|gerne?)|(?:lieber|am liebsten|gerne?) (?:nicht|nie))) tot sein\\b"
  ],
  historical: [
    "\\b(?:fr\xFCher war ich|ich war fr\xFCher) suizidal\\b",
    "\\bfr\xFCher wollte ich (?:sterben|mich umbringen|mir (?:etwas|was|selbst etwas) antun)\\b",
    "\\bmein(?:e|en|er|em|es)? (?:suizid|selbstmord)(?:plan|pl\xE4ne|plaene) (?:ist von vor (?:jahren|monaten)|wurde[n]? vor (?:jahren|monaten) aufgegeben)\\b",
    "\\bfr\xFCher hatte ich (?:suizid|selbstmord)gedanken\\b",
    "\\bfr\xFCher hatte ich (?:suizidal(?:e|en) gedanken|gedanken an (?:selbstmord|suizid))\\b",
    "\\b(?:fr\xFCher|frueher|damals|vor jahren|letztes jahr) (?:w\xFCnschte|wuenschte|w\xFCnsche|wuensche) ich(?: mir)?(?:, ?| )(?:ich (?:w\xE4re|waere)(?: (?:lieber|am liebsten|gerne?))? tot|dass ich(?: (?:lieber|am liebsten|gerne?))? tot (?:w\xE4re|waere)|(?:lieber )?tot zu sein)\\b",
    "\\bich (?:w\xFCnschte|wuenschte|w\xFCnsche|wuensche)(?: mir)? (?:fr\xFCher|frueher|damals|vor jahren|letztes jahr)(?:, ?| )(?:ich (?:w\xE4re|waere)(?: (?:lieber|am liebsten|gerne?))? tot|dass ich(?: (?:lieber|am liebsten|gerne?))? tot (?:w\xE4re|waere)|(?:lieber )?tot zu sein)\\b",
    "\\bich habe mir (?:fr\xFCher|frueher|damals|vor jahren|letztes jahr) (?:gew\xFCnscht|gewuenscht)(?:, ?| )(?:ich (?:w\xE4re|waere)(?: (?:lieber|am liebsten|gerne?))? tot|dass ich(?: (?:lieber|am liebsten|gerne?))? tot (?:w\xE4re|waere)|(?:lieber )?tot zu sein)\\b",
    "\\b(?:ich (?:w\xE4re|waere) (?:fr\xFCher|frueher|damals|vor jahren|letztes jahr)|(?:fr\xFCher|frueher|damals|vor jahren|letztes jahr) (?:w\xE4re|waere) ich) (?:lieber|am liebsten|gerne?) tot(?: gewesen)?\\b",
    `\\b(?:(?:fr\xFCher|frueher|damals|vor jahren|letztes jahr) (?:dachte|sagte) ich|ich (?:dachte|sagte) (?:fr\xFCher|frueher|damals|vor jahren|letztes jahr))(?:[:,] ?| )["\u201E\u201C'\xAB\xBB]?(?:ich (?:w\xE4re|waere)(?: (?:jetzt|gerade|einfach))? (?:lieber|am liebsten|gerne?) tot|(?:lieber|am liebsten|gerne?) (?:w\xE4re|waere) ich(?: (?:jetzt|gerade))? tot|ich (?:w\xFCnschte|wuenschte|w\xFCnsche|wuensche)(?: mir)?(?:, ?| )(?:ich (?:w\xE4re|waere)(?: (?:lieber|am liebsten|gerne?))? tot|dass ich(?: (?:lieber|am liebsten|gerne?))? tot (?:w\xE4re|waere)|(?:lieber )?tot zu sein)|ich (?:will|m\xF6chte|moechte|(?:w\xFCrde|wuerde) (?:lieber|am liebsten|gerne?))(?: lieber)? tot sein)\\b["\u201C\u201D'\xBB\xAB]?`,
    "\\b(?:ich (?:w\xE4re|waere)(?: (?:jetzt|gerade|einfach))? (?:lieber|am liebsten|gerne?) tot|(?:lieber|am liebsten|gerne?) (?:w\xE4re|waere) ich(?: (?:jetzt|gerade))? tot) gewesen\\b",
    "\\b(?:ich (?:w\xE4re|waere)(?: (?:jetzt|gerade|einfach))? (?:lieber|am liebsten|gerne?) tot|(?:lieber|am liebsten|gerne?) (?:w\xE4re|waere) ich(?: (?:jetzt|gerade))? tot|ich (?:w\xFCnschte|wuenschte|w\xFCnsche|wuensche)(?: mir)?(?:, ?| )(?:ich (?:w\xE4re|waere)(?: (?:lieber|am liebsten|gerne?))? tot|dass ich(?: (?:lieber|am liebsten|gerne?))? tot (?:w\xE4re|waere)|(?:lieber )?tot zu sein)|ich (?:will|m\xF6chte|moechte|(?:w\xFCrde|wuerde) (?:lieber|am liebsten|gerne?))(?: lieber)? tot sein)(?:, ?| )als ich (?:ein kind|jung) war\\b"
  ],
  uncertain: [
    "\\bich wei\xDF nicht,? ob ich suizidal bin\\b",
    "\\bich bin (?:mir )?nicht sicher,? ob ich suizidal bin\\b",
    '\\b(?:der titel|der ausdruck) ["\\u201e]?mein(?:e|en|er|em|es)? (?:suizid|selbstmord)(?:plan|pl\xE4ne|plaene)["\\u201c]?',
    `\\b(?:(?:er|sie|(?:mein|meine|ein|eine|der|die) (?:freund|freundin|partner|partnerin|bruder|schwester|erz\xE4hler|figur)) (?:sagte zu mir|sagt|sagte|schreibt|schrieb|dachte|denkt|erz\xE4hlte mir|erz\xE4hlt mir)|ich (?:las|lese|h\xF6rte|h\xF6re|zitiere|habe nie gesagt|habe nicht gesagt)|(?:der|die|das) (?:satz|aussage|zitat|ausdruck|phrase)|was bedeutet|was hei\xDFt|was heisst|die bedeutung von|(?:im|in einem|in dem) (?:buch|film|roman|artikel|lied) (?:steht|hei\xDFt es))(?:[:,] ?| )["\u201E\u201C'\xAB\xBB]?(?:ich (?:w\xE4re|waere)(?: (?:jetzt|gerade|einfach))? (?:lieber|am liebsten|gerne?) tot|(?:lieber|am liebsten|gerne?) (?:w\xE4re|waere) ich(?: (?:jetzt|gerade))? tot|ich (?:w\xFCnschte|wuenschte|w\xFCnsche|wuensche)(?: mir)?(?:, ?| )(?:ich (?:w\xE4re|waere)(?: (?:lieber|am liebsten|gerne?))? tot|dass ich(?: (?:lieber|am liebsten|gerne?))? tot (?:w\xE4re|waere)|(?:lieber )?tot zu sein)|ich (?:will|m\xF6chte|moechte|(?:w\xFCrde|wuerde) (?:lieber|am liebsten|gerne?))(?: lieber)? tot sein)\\b["\u201C\u201D'\xBB\xAB]?`,
    `^["\u201E\u201C'\xAB\xBB](?:ich (?:w\xE4re|waere)(?: (?:jetzt|gerade|einfach))? (?:lieber|am liebsten|gerne?) tot|(?:lieber|am liebsten|gerne?) (?:w\xE4re|waere) ich(?: (?:jetzt|gerade))? tot|ich (?:w\xFCnschte|wuenschte|w\xFCnsche|wuensche)(?: mir)?(?:, ?| )(?:ich (?:w\xE4re|waere)(?: (?:lieber|am liebsten|gerne?))? tot|dass ich(?: (?:lieber|am liebsten|gerne?))? tot (?:w\xE4re|waere)|(?:lieber )?tot zu sein)|ich (?:will|m\xF6chte|moechte|(?:w\xFCrde|wuerde) (?:lieber|am liebsten|gerne?))(?: lieber)? tot sein)[.!?]?["\u201C\u201D'\xBB\xAB][.!?]?$`,
    `["\u201E\u201C'\xAB\xBB](?:ich (?:w\xE4re|waere)(?: (?:jetzt|gerade|einfach))? (?:lieber|am liebsten|gerne?) tot|(?:lieber|am liebsten|gerne?) (?:w\xE4re|waere) ich(?: (?:jetzt|gerade))? tot|ich (?:w\xFCnschte|wuenschte|w\xFCnsche|wuensche)(?: mir)?(?:, ?| )(?:ich (?:w\xE4re|waere)(?: (?:lieber|am liebsten|gerne?))? tot|dass ich(?: (?:lieber|am liebsten|gerne?))? tot (?:w\xE4re|waere)|(?:lieber )?tot zu sein)|ich (?:will|m\xF6chte|moechte|(?:w\xFCrde|wuerde) (?:lieber|am liebsten|gerne?))(?: lieber)? tot sein)[.!?]?["\u201C\u201D'\xBB\xAB] (?:ist|war|steht|stammt|kommt) (?:(?:nur |lediglich )?(?:ein|der|das) (?:satz|zitat|ausspruch) )?(?:aus|in) (?:einem|dem|einer|der) (?:film|buch|roman|geschichte|artikel|lied)\\b`,
    "\\bich (?:glaube|denke|finde) nicht(?:[:,] ?| )(?:dass )?(?:ich (?:w\xE4re|waere)(?: (?:jetzt|gerade|einfach))? (?:lieber|am liebsten|gerne?) tot|(?:lieber|am liebsten|gerne?) (?:w\xE4re|waere) ich(?: (?:jetzt|gerade))? tot|ich (?:w\xFCnschte|wuenschte|w\xFCnsche|wuensche)(?: mir)?(?:, ?| )(?:ich (?:w\xE4re|waere)(?: (?:lieber|am liebsten|gerne?))? tot|dass ich(?: (?:lieber|am liebsten|gerne?))? tot (?:w\xE4re|waere)|(?:lieber )?tot zu sein)|ich (?:will|m\xF6chte|moechte|(?:w\xFCrde|wuerde) (?:lieber|am liebsten|gerne?))(?: lieber)? tot sein)\\b"
  ],
  continuedRisk: "\\b(?:aber|und) (?:ich )?(?:bin es noch|bin immer noch|f\xFChle mich immer noch so|tue es noch)\\b",
  conditional: "\\b(?:wenn|falls|bis|es sei denn|nicht sicher)\\b"
};

// ../../../packages/safety/crisisDetector.ts
var CRISIS_KEYWORDS = [
  "suicide",
  "suicidal",
  "kill myself",
  "hurt myself",
  "end my life",
  "want to die",
  "don't want to live",
  "do not want to live",
  "selbstmord",
  "suizid",
  "mich umbringen",
  "mir etwas antun",
  "mir selbst schaden",
  "nicht mehr leben",
  "sterben will",
  "will sterben",
  "intihar",
  "kendime zarar",
  "can\u0131ma k\u0131ymak",
  "ya\u015Famak istemiyorum",
  "\xF6lmek istiyorum",
  "hayat\u0131ma son vermek",
  "kendimi asmak",
  "ila\xE7 i\xE7ip \xF6lmek"
];
function contextualCrisisContext(text, policy) {
  let value = text.normalize("NFC").toLowerCase().replace(/’/g, "'").replace(/\s+/g, " ").trim();
  if (!new RegExp(policy.signal, "u").test(value)) return { signal: false, context: "NONE" };
  const observed = /* @__PURE__ */ new Set();
  for (const kind of ["reassurance", "historical", "uncertain"]) {
    for (const pattern of policy[kind]) {
      const rule = new RegExp(pattern, "gu");
      if (rule.test(value)) {
        observed.add(kind);
        value = value.replace(new RegExp(pattern, "gu"), " ");
      }
    }
  }
  if ([policy.selfDirected, policy.currentState].some((pattern) => new RegExp(pattern, "u").test(value))) return { signal: true, context: "CURRENT_RISK_SIGNAL" };
  if (observed.size && new RegExp(policy.continuedRisk, "u").test(value)) return { signal: true, context: "CONTINUING_RISK_SIGNAL" };
  if (new RegExp(policy.signal, "u").test(value)) return { signal: false, context: "UNCERTAIN" };
  if (observed.size && new RegExp(policy.conditional, "u").test(value)) return { signal: false, context: "UNCERTAIN" };
  return { signal: false, context: observed.has("uncertain") ? "UNCERTAIN" : observed.has("historical") ? "HISTORICAL" : "REASSURANCE" };
}
function englishCrisisContext(text) {
  return contextualCrisisContext(text, english_crisis_default);
}
function germanCrisisContext(text) {
  return contextualCrisisContext(text, german_crisis_default);
}
function normalizeCrisisText(text, turkish = true) {
  const composed = text.normalize("NFC");
  const lower = turkish ? composed.toLocaleLowerCase("tr-TR") : composed.toLowerCase();
  return lower.replace(/i\u0307/g, "i").normalize("NFC");
}
function checkCrisisTrigger(text, isMoving = false) {
  const candidates = [normalizeCrisisText(text), normalizeCrisisText(text, false)];
  const urgentSafety = Object.values(urgent_safety_default).some((pair) => pair.every((pattern) => new RegExp(pattern, "u").test(candidates[1])));
  const english = englishCrisisContext(text);
  const german = germanCrisisContext(text);
  const contextualKeywords = /* @__PURE__ */ new Set([...english_crisis_default.legacyKeywords, ...german_crisis_default.legacyKeywords]);
  const selfHarmSignal = english.signal || german.signal || CRISIS_KEYWORDS.filter((keyword) => !contextualKeywords.has(keyword)).some((keyword) => candidates.some((candidate) => candidate.includes(normalizeCrisisText(keyword))));
  if (urgentSafety || selfHarmSignal) {
    if (isMoving) {
      return {
        isCrisis: true,
        emergencyResponseTr: "S\xF6yledikleriniz benim i\xE7in \xE7ok \xF6nemli ve zor bir andan ge\xE7ti\u011Finizi anl\u0131yorum. Ancak ben acil durum servisi de\u011Filim. L\xFCtfen ekrana bakmay\u0131n. M\xFCmk\xFCn oldu\u011Funda arac\u0131n\u0131z\u0131 hemen g\xFCvenli bir yerde durdurun ve 112 Acil \xC7a\u011Fr\u0131 Merkezini aray\u0131n. Yaln\u0131z de\u011Filsiniz."
      };
    }
    return {
      isCrisis: true,
      emergencyResponseTr: "S\xF6yledikleriniz benim i\xE7in \xE7ok \xF6nemli ve \u015Fu an \xE7ok zor bir s\xFCre\xE7ten ge\xE7ti\u011Finizi anl\u0131yorum. Ancak ben bir acil durum veya sa\u011Fl\u0131k servisi de\u011Filim. L\xFCtfen \u015Fu an g\xFCvende kalmak i\xE7in gecikmeden 112 Acil \xC7a\u011Fr\u0131 Merkezi ile ileti\u015Fime ge\xE7in. Yaln\u0131z de\u011Filsiniz, profesyonel uzmanlar size yard\u0131mc\u0131 olmak i\xE7in haz\u0131r."
    };
  }
  return { isCrisis: false, riskLevel: [english, german].some((r) => ["UNCERTAIN", "HISTORICAL"].includes(r.context)) ? "UNCERTAIN" : "NONE" };
}
export {
  CRISIS_KEYWORDS,
  checkCrisisTrigger,
  englishCrisisContext,
  germanCrisisContext,
  normalizeCrisisText
};
