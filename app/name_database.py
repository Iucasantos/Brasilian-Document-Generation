import random

NAME_CONNECTORS = {"da", "de", "do", "das", "dos"}

FEMALE_NAMES = (
    "Alice", "Ana", "Beatriz", "Camila", "Carolina", "Cecília", "Clara",
    "Daniela", "Débora", "Eduarda", "Elisa", "Fernanda", "Gabriela",
    "Giovanna", "Helena", "Heloísa", "Isabela", "Isadora", "Jéssica",
    "Júlia", "Juliana", "Lara", "Larissa", "Laura", "Letícia",
    "Lívia", "Luana", "Luísa", "Manuela", "Marcela", "Maria",
    "Mariana", "Marina", "Melissa", "Natália", "Nicole", "Olívia",
    "Paloma", "Rafaela", "Rebeca", "Sabrina", "Sara", "Sofia",
    "Taís", "Valentina", "Vanessa", "Vitória", "Yasmin", "Bianca", "Bruna",
)

MALE_NAMES = (
    "Alexandre", "André", "Antônio", "Arthur", "Bernardo", "Bruno",
    "Caio", "Daniel", "Danilo", "Davi", "Diego", "Diogo", "Eduardo",
    "Emanuel", "Enzo", "Felipe", "Fernando", "Francisco", "Gabriel",
    "Guilherme", "Gustavo", "Heitor", "Henrique", "Ian", "Igor",
    "Isaac", "João", "Joaquim", "Jonas", "Leonardo", "Lorenzo",
    "Lucas", "Leandro", "Matheus", "Miguel", "Murilo", "Nicolas",
    "Otávio", "Pedro", "Rafael", "Raul", "Renan", "Rodrigo",
    "Samuel", "Theo", "Thiago", "Tomás", "Vicente", "Vinícius", "Yuri",
)

SURNAMES = (
    "Abreu", "Albuquerque", "Alencar", "Almeida", "Alves", "Amaral", "Andrade",
    "Antunes", "Araújo", "Arruda", "Assis", "Azevedo", "Barbosa", "Barros",
    "Bastos", "Batista", "Borges", "Braga", "Branco", "Brito", "Campos",
    "Cardoso", "Carneiro", "Carvalho", "Castro", "Cavalcanti", "Coelho",
    "Correia", "Costa", "Coutinho", "Cruz", "Cunha", "Dias", "Diniz",
    "Duarte", "Farias", "Fernandes", "Ferreira", "Figueiredo", "Fonseca",
    "Franco", "Freitas", "Garcia", "Gomes", "Gonçalves", "Guedes", "Guerra",
    "Henriques", "Lima", "Lins", "Lopes", "Lourenço", "Macedo", "Machado",
    "Magalhães", "Marques", "Martins", "Medeiros", "Mello", "Mendes",
    "Miranda", "Monteiro", "Moraes", "Moreira", "Moura", "Nascimento",
    "Neves", "Nogueira", "Nunes", "Oliveira", "Pacheco", "Paiva", "Passos",
    "Peixoto", "Pereira", "Pinheiro", "Pinto", "Pires", "Prado", "Ramos",
    "Reis", "Ribeiro", "Rocha", "Rodrigues", "Santana", "Santos", "Saraiva",
    "Silva", "Silveira", "Siqueira", "Soares", "Sousa", "Tavares", "Teixeira",
    "Toledo", "Torres", "Valente", "Vargas", "Vasconcelos", "Vieira",
)


def normalize_person_name(value: str) -> str:
    words = value.strip().split()
    return " ".join(
        word.casefold()
        if word.casefold() in NAME_CONNECTORS
        else word[:1].upper() + word[1:].lower()
        for word in words
    )


def complete_custom_name(value: str) -> str:
    words = value.strip().split()
    significant_count = sum(
        word.casefold() not in NAME_CONNECTORS for word in words
    )
    used_words = {word.casefold() for word in words}
    for surname in SURNAMES:
        if significant_count >= 4:
            break
        if surname.casefold() in used_words:
            continue
        words.append(surname)
        used_words.add(surname.casefold())
        significant_count += 1
    return normalize_person_name(" ".join(words))


def generate_name(sex: str, *, rng: random.Random | None = None) -> str:
    if sex not in {"M", "F"}:
        raise ValueError("Sex must be either M or F.")

    random_source = rng if rng is not None else random.Random()
    first_name = random_source.choice(FEMALE_NAMES if sex == "F" else MALE_NAMES)
    surnames = random_source.sample(SURNAMES, 3)
    return normalize_person_name(" ".join((first_name, *surnames)))
