PERSONA = "4-year-old boy, showing signs of being nerdy"
PREFERRED_BRANCH = "Noe Valley"

SUMMARIES = [
    (
        "Leo asked about why dinosaurs went extinct and whether any are still "
        "alive. He also wanted to know if robots can think."
    ),
    (
        "Leo spent most of the call talking about space. He wanted to know how "
        "far away the moon is, whether people live on Mars, and what happens "
        "if you fall into a black hole."
    ),
    (
        "Leo asked why volcanoes explode and whether lava is hotter than the "
        "sun. He also asked about bugs — specifically why ants can carry things "
        "bigger than themselves."
    ),
    (
        "Leo was curious about how cars work and why some cars don't need gas. "
        "He also asked if animals can talk to each other."
    ),
]


def load_interests():
    return {"persona": PERSONA, "summaries": SUMMARIES, "preferred_branch": PREFERRED_BRANCH}
