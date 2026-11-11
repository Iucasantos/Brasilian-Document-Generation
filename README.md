# Brasilian-Document-Generation

Um programa responsável por gerar famílias inteiras e os documentos de cada uma dessas pessoas, simulando uma família.

Atualmente o programa é capaz de gerar 4 tipos de documentos: CIN, CNH, certidão de casamento(quando gerado casais), certidão de nascimento e um comprovante de residência extremamente simples.

## Configuração inicial do programa

Nesse site, em code, o botão azul no meio baixe o arquivo zip do programa

Extraia a pasta do programa do arquivo .zip

Execute `setup.bat` primeiro, ele irá realizar as configurações iniciais do programa e fechará e se excluirá sozinho após instalar tudo que é necessário, deixando o programa pronto para uso caso o usuário não saiba mexer com código

CASO a disconfiança for grande e sabe mexer no código de forma alternativa você pode apenas rodar terminal do programa:

```bash
py -m venv .venv
```

```bash
.venv/scripts/activate
```

```bash
python -m pip install
```

```bash
pip install -r requirements.txt
```

## Executando o programa

Após a configuração inicial, para iniciar o programa execute `run.bat` ele abrirá um CMD com o programa rodando

TODO DOCUMENTO SERÁ GERADO NA PASTA `output`

## Usando o programa

A primeira tela a aparecer no programa será:

```text
===========================================
1 - Random Generation
2 - Custom Generation
===========================================
>> 
```

A navegação se deve inserindo o `número` correspondente á sua escolha, neste caso, digitando 1 e apertando enter levará o usuário á Random Generation, onde os documentos serão gerados automaticamente de duas diferentes maneiras, já se o usuário digitar 2 e então enter ele selecionará a opção de gerar manualmente uma família, escolhendo os membros, nomes, idades entre outras informações, pode soar demorado, mas há uma funcionalidade especial no programa que agiliza as coisas.

## Modos de geração de família

Como dito anteriormente existem inicialmente dois tipos de geração:

### Random Generation

Ao selecionar essa opção o usuário será levado a mais uma escolha:

```text
===========================================
1 - Geração única
2 - Geração em batch
===========================================
>> 
```

 - `Geração Única`: o usuário seleciona quantos membros de família ele deseja gerar
 - `Geração em batch`: o usuário seleciona quantas famílias ele deseja gerar, todos os membros serão adicionados de forma aleatória

### Custom generation

Aqui o usuário poderá gerar uma familia por vez, mas com a diferença de que ele poderá escolher quantos membros cada família tem e os dados de cada membro, se ele gerar uma família de 8 pessoas(2 parentes, 1 cônjugue e 5 filhos) ele terá que passar a informação de cada um, o que pode ser um pouco chato em uma situação em que o usuário só precisa do nome inicial, idade e sexo específico, mas para isso foi gerada uma solução.

## Parcial randomization

Em variadas situações foi adicionado a possibilidade de gerar uma resposta aleatória para agilizar o processo de geração de documento, sendo elas:

 - Em `Geração em batch`, apenas apertar enter sem escolher um número irá gerar 10 famílias
 - Em `Custom Generation`, o usuário pode digitar apenas o nome inicial que apertando enter o programa autocompleta. Por exemplo o usuário digita `wesley` para nome e o programa devolve `Wesley Magalhães Peixoto Dias` no documento. 
 - Em todos os dados perguntados pelo programa em `Custom Generation` e também nome, o usuário pode apenas apertar enter para gerar de forma aleatória mas organizada um dado para o membro, então caso precise fornecer nome, idade, sexo, estado e cidade, se o usuário precisar apenas de sexo e idade ele poder apertar enter no resto que será gerado sem problema no documento.

todos essas pequenas facilitações foram feitas para facilitar a vida do usuário na geração de documentos sintéticos.
