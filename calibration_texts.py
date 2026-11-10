"""
The Milestone 4 calibration texts. `python calibrate.py` scores them.

Not my own writing. That's kept for the criteria tests in unit 8, so the
weights and thresholds aren't tuned on the texts that will judge them.

Human texts are public-domain passages from Project Gutenberg, taken from
away from each book's famous passages, since GPT-2 may have memorised those and
they'd look machine-predictable for the wrong reason. Line breaks are joined
and "[Picture: ...]" markers removed; otherwise they're verbatim.

AI texts were written by Claude (claude-opus-5-5) for this calibration, so
they're genuinely machine-generated, though all by ONE model, which is a
limit worth remembering. `ai_lightly_edited` is `ai_advice` with small hand
edits of the kind a person tidying it up might make: contractions, a few
word swaps, an aside in brackets, one typo.
"""

TEXTS = {
    # ── clearly AI ──────────────────────────────────────────────────────────
    "ai_expository": (
        "Remote work has fundamentally reshaped the way many organizations operate. "
        "By removing the need for a daily commute, it gives employees more time and "
        "flexibility, which can lead to higher job satisfaction and improved "
        "productivity. At the same time, it presents unique challenges. Teams must "
        "find new ways to communicate effectively, maintain a sense of connection, "
        "and ensure that important information is shared consistently. Managers, in "
        "particular, need to shift their focus from monitoring activity to measuring "
        "outcomes. Additionally, companies must invest in the right tools and "
        "infrastructure, such as secure video conferencing platforms and "
        "collaborative project management software. It is also important to "
        "consider the impact on company culture, as informal interactions that once "
        "happened naturally in the office now require deliberate effort. Ultimately, "
        "the success of remote work depends on a thoughtful balance between autonomy "
        "and structure. Organizations that approach it strategically, with clear "
        "expectations and ongoing support for their employees, are well positioned "
        "to benefit from this evolving model of work."
    ),
    "ai_narrative": (
        "The first winter I spent in Chicago taught me more about resilience than "
        "any class I had ever taken. I had moved there in early January, full of "
        "excitement about my new job and the opportunities that the city seemed to "
        "offer. What I was not prepared for was the cold. The wind off Lake Michigan "
        "cut through every layer I owned, and the gray skies seemed to stretch on "
        "endlessly. At first, I felt isolated and overwhelmed. However, as the weeks "
        "passed, I began to find small ways to make the city feel like home. I "
        "discovered a cozy coffee shop around the corner from my apartment, where "
        "the barista quickly learned my order. I joined a weekend running group that "
        "met no matter how low the temperature dropped. Slowly, the city that had "
        "once felt so harsh began to reveal its warmth. Looking back, that difficult "
        "season helped me grow in ways I never expected, and it reminded me that a "
        "sense of belonging is often something we build rather than something we find."
    ),
    "ai_advice": (
        "Learning a new language as an adult can feel overwhelming, but with the "
        "right approach, it is entirely achievable. The key is consistency. Rather "
        "than studying for several hours once a week, it is far more effective to "
        "practice for twenty or thirty minutes every day. This helps reinforce new "
        "vocabulary and keeps the language fresh in your mind. In addition, it is "
        "important to engage with the language in a variety of ways. Listening to "
        "podcasts, watching television shows with subtitles, and reading short "
        "articles can all help you develop a more natural understanding of how the "
        "language is used. Speaking practice is equally essential. Many learners "
        "hesitate to speak because they are afraid of making mistakes, but mistakes "
        "are a natural and valuable part of the learning process. Language exchange "
        "partners and online tutoring platforms provide excellent opportunities to "
        "build confidence in a supportive environment. Finally, remember to "
        "celebrate your progress along the way. Every new word and every successful "
        "conversation is a step toward fluency."
    ),

    # ── lightly-edited AI (ai_advice, hand-edited) ───────────────────────────
    "ai_lightly_edited": (
        "Learning a new language as an adult can feel overwhelming, but with the "
        "right approach it's entirely doable. The key is consistency. Rather than "
        "studying for hours once a week, it's much more effective to practice for "
        "twenty or thirty minutes every day. This helps new vocabulary stick and "
        "keeps the language fresh in your mind. It's also important to engage with "
        "the language in different ways. Listening to podcasts, watching shows with "
        "subtitles, and reading short articles can all help you get a more natural "
        "feel for how the language is used. Speaking practice is just as essential. "
        "Lots of learners hesitate to speak because they're afraid of making "
        "mistakes (I certainly was), but mistakes are a natural part of the learning "
        "process. Language exchange partners and online tutors are great for "
        "building confidence in a supportive environment. Finally, remember to "
        "celebrate your progress. Every new word and every succesful conversation "
        "is a step toward fluency."
    ),

    # ── clearly human, casual — Jerome K. Jerome, Three Men in a Boat (1889), ch. XIII
    "human_casual": (
        "We got up tolerably early on the Monday morning at Marlow, and went for a "
        "bathe before breakfast; and, coming back, Montmorency made an awful ass of "
        "himself. The only subject on which Montmorency and I have any serious "
        "difference of opinion is cats. I like cats; Montmorency does not.\n\n"
        "When I meet a cat, I say, “Poor Pussy!” and stop down and tickle the side "
        "of its head; and the cat sticks up its tail in a rigid, cast-iron manner, "
        "arches its back, and wipes its nose up against my trousers; and all is "
        "gentleness and peace. When Montmorency meets a cat, the whole street knows "
        "about it; and there is enough bad language wasted in ten seconds to last "
        "an ordinarily respectable man all his life, with care.\n\n"
        "I do not blame the dog (contenting myself, as a rule, with merely clouting "
        "his head or throwing stones at him), because I take it that it is his "
        "nature. Fox-terriers are born with about four times as much original sin "
        "in them as other dogs are, and it will take years and years of patient "
        "effort on the part of us Christians to bring about any appreciable "
        "reformation in the rowdiness of the fox-terrier nature.\n\n"
        "I remember being in the lobby of the Haymarket Stores one day, and all "
        "round about me were dogs, waiting for the return of their owners, who were "
        "shopping inside. There were a mastiff, and one or two collies, and a St. "
        "Bernard, a few retrievers and Newfoundlands, a boar-hound, a French "
        "poodle, with plenty of hair round its head, but mangy about the middle; a "
        "bull-dog, a few Lowther Arcade sort of animals, about the size of rats, "
        "and a couple of Yorkshire tykes.\n\n"
        "There they sat, patient, good, and thoughtful. A solemn peacefulness "
        "seemed to reign in that lobby. An air of calmness and resignation—of "
        "gentle sadness pervaded the room.\n\n"
        "Then a sweet young lady entered, leading a meek-looking little "
        "fox-terrier, and left him, chained up there, between the bull-dog and the "
        "poodle. He sat and looked about him for a minute. Then he cast up his "
        "eyes to the ceiling, and seemed, judging from his expression, to be "
        "thinking of his mother. Then he yawned. Then he looked round at the other "
        "dogs, all silent, grave, and dignified."
    ),

    # ── plain human — Booker T. Washington, Up from Slavery (1901), ch. III
    "human_plain": (
        "After hearing of the Hampton Institute, I continued to work for a few "
        "months longer in the coal-mine. While at work there, I heard of a vacant "
        "position in the household of General Lewis Ruffner, the owner of the "
        "salt-furnace and coal-mine. Mrs. Viola Ruffner, the wife of General "
        "Ruffner, was a “Yankee” woman from Vermont. Mrs. Ruffner had a reputation "
        "all through the vicinity for being very strict with her servants, and "
        "especially with the boys who tried to serve her. Few of them remained with "
        "her more than two or three weeks. They all left with the same excuse: she "
        "was too strict. I decided, however, that I would rather try Mrs. "
        "Ruffner’s house than remain in the coal-mine, and so my mother applied to "
        "her for the vacant position. I was hired at a salary of $5 per month.\n\n"
        "I had heard so much about Mrs. Ruffner’s severity that I was almost "
        "afraid to see her, and trembled when I went into her presence. I had not "
        "lived with her many weeks, however, before I began to understand her. I "
        "soon began to learn that, first of all, she wanted everything kept clean "
        "about her, that she wanted things done promptly and systematically, and "
        "that at the bottom of everything she wanted absolute honesty and "
        "frankness. Nothing must be sloven or slipshod; every door, every fence, "
        "must be kept in repair."
    ),

    # ── formal human — J. S. Mill, On Liberty (1859), ch. III, 2nd paragraph
    "human_formal": (
        "In maintaining this principle, the greatest difficulty to be encountered "
        "does not lie in the appreciation of means towards an acknowledged end, but "
        "in the indifference of persons in general to the end itself. If it were "
        "felt that the free development of individuality is one of the leading "
        "essentials of well-being; that it is not only a co-ordinate element with "
        "all that is designated by the terms civilisation, instruction, education, "
        "culture, but is itself a necessary part and condition of all those "
        "things; there would be no danger that liberty should be under-valued, and "
        "the adjustment of the boundaries between it and social control would "
        "present no extraordinary difficulty. But the evil is, that individual "
        "spontaneity is hardly recognised by the common modes of thinking, as "
        "having any intrinsic worth, or deserving any regard on its own account. "
        "The majority, being satisfied with the ways of mankind as they now are "
        "(for it is they who make them what they are), cannot comprehend why those "
        "ways should not be good enough for everybody; and what is more, "
        "spontaneity forms no part of the ideal of the majority of moral and "
        "social reformers, but is rather looked on with jealousy, as a troublesome "
        "and perhaps rebellious obstruction to the general acceptance of what "
        "these reformers, in their own judgment, think would be best for mankind."
    ),
}

SOURCES = {
    "human_casual": "Jerome K. Jerome, Three Men in a Boat (1889), ch. XIII — Project Gutenberg #308",
    "human_plain": "Booker T. Washington, Up from Slavery (1901), ch. III — Project Gutenberg #2376",
    "human_formal": "John Stuart Mill, On Liberty (1859), ch. III — Project Gutenberg #34901",
}
