# Locais de votação

Estado em 2026-10-28: download, tratamento Turi e entidade `LocalVotacao`
implementados. O mapa de setas, a comparação de duas bases e sua API também estão
implementados em `/guinada`; veja o
[contrato do mapa](../../../../docs/vote_shift_map.md).

## Fontes e cobertura temporal

`apps/turi/src/downloaders/tse_voting_locations.py` instancia o `Downloader`
padrão, sem sobrescrever conversão ou exigir nomes/quantidades de membros do ZIP.
As URLs usam `TSE_ELECTION_YEARS`, a mesma configuração dos downloads eleitorais.
Na configuração e carga atuais, a lista contém 2018, 2020, 2022 e 2026.
O cache do downloader vale quatro semanas e não é invalidado automaticamente
quando a lista de anos muda. Em 28/10, foi necessário baixar explicitamente o
pacote de 2026: o cache de 26/10 ainda apontava apenas para os três anos antigos.

O downloader converte os CSVs do ZIP para Parquet usando `;` e ISO-8859-1.
O produtor lê todos os Parquets disponíveis na pasta, normaliza cada layout antes
de concatenar e deduplica os dados. Não depende da divisão por UF nem da presença
de um arquivo nacional. Sobreposição entre arquivos não multiplica os locais.

Linhas de `SG_UF = ZZ` são excluídas porque o catálogo é do Brasil. Não há filtro
de cargo, quantidade de eleitores ou situação cadastral. Não são armazenados os
quantitativos do eleitorado nem uma linha por seção. Identidade e metadados
eleitorais inválidos interrompem o produtor, preservando as saídas anteriores.

## Identidade e histórico

O ID uint64 é o hash Polars, com a seed compartilhada do projeto, da struct:

```text
uf + codigo_municipio_tse + zona_eleitoral + numero
```

Município TSE, zona e número do local são normalizados numericamente e armazenados
como strings, eliminando diferenças de zeros à esquerda. O código municipal IBGE
é associado pelo mapeamento TSE/IBGE existente. Ausência no mapeamento preserva o
local e o código TSE, deixando `codigo_municipio_ibge` nulo.

O ID representa uma identidade cadastral eleitoral, sem garantir permanência do
prédio entre anos. Uma escola cadastrada em zonas diferentes pode ter IDs distintos.
Não usar apenas o número do local, o nome ou `codigo_local` do item do BU.

Há duas saídas, ambas com os campos de `LocalVotacao`:

| Dataset | Chave e conteúdo |
|---|---|
| `opendata_voting_location/tse.parquet` | Uma linha por `id`, com a observação eleitoral mais recente disponível |
| `opendata_voting_location_history/tse.parquet` | Uma linha por `id`, `data_eleicao` e `numero_turno`, mantendo os dados de cada observação |

O catálogo inclui locais que só aparecem em anos antigos; não equivale a uma lista
de locais atualmente ativos. Ano, data e turno não entram no ID cadastral, mas
permanecem nos registros. `data_geracao` preserva a data/hora informada pelo TSE,
sem atribuir um fuso que o arquivo não informa.

Quando existem snapshots diferentes da mesma observação, prevalece a geração
mais recente. Seções dessa geração são consolidadas sem escolher arbitrariamente
um endereço: valores não nulos divergentes deixam o respectivo campo nulo e
entram em `campos_divergentes`. Se uma coordenada divergir, o par inteiro fica
nulo. Os valores originais continuam nos Parquets brutos.

As colunas de local original do arquivo TSE descrevem relações das seções antes
de transferências; não substituem `NR_LOCAL_VOTACAO` na identidade consolidada.
Continuam disponíveis nos brutos, sem serem reduzidas a uma relação única que
poderia ser falsa.

## Endereço e coordenadas

O registro preserva `nome`, `endereco`, `bairro`, `cep`, `latitude_tse` e
`longitude_tse`. Coordenadas aceitam ponto ou vírgula decimal e permanecem
identificadas como informação do TSE, sem serem sobrescritas pelas do IBGE.
Ausência, sentinela `-1`, valores não finitos, fora dos limites WGS84 ou o par
`0,0` tornam o par nulo. Latitude zero com longitude válida é preservada.

`endereco_cluster_id` é opcional. Quando o cadastro de endereços IBGE está
disponível, o produtor procura o cluster existente por município IBGE, CEP e
número predial explícito no final do endereço. Não usa número de rodovia ou
quilômetro como número de prédio. Só associa chaves que resolvem um único cluster;
não fabrica um hash de endereço para encobrir ausência ou ambiguidade.

Sem cadastro IBGE ou correspondência suficiente, o cluster permanece nulo e as
coordenadas TSE continuam disponíveis como fallback. O consumidor pode resolver
as coordenadas do cluster e, na ausência delas, usar o par TSE. Deve escolher o
par da mesma origem, sem misturar latitude de uma fonte e longitude de outra.

## Execução

Da raiz, para baixar os anos configurados e gerar somente estes datasets:

```bash
PYTHONPATH=apps/turi/src:. uv run python -m scripts.operations.voting_locations.locations --download
```

Para reutilizar os brutos existentes, omita `--download`. O comando isolado
executa o tratamento diretamente, sem a janela de execução do `DataScript`.
`--download` respeita o cache. Na atualização incremental de 2026, foi chamado
`tse_voting_locations_downloader.download_from_sources("zip", "application/zip",
sources_override=[url_2026], is_retry=True)` antes do script sem `--download`.
Isso acrescentou o pacote ausente sem apagar os arquivos dos anos anteriores.

Os entrypoints de downloads e dumps também registram a operação. O cron usa
`ELECTIONS_LIFETIME`. Esses entrypoints contêm outras operações ativas do usuário;
não são equivalentes ao comando isolado. No entrypoint de dumps, a manutenção
de Bloom filters ocorre depois dos produtores e inclui os novos datasets.

Cada Parquet é preparado em temporário no mesmo diretório e substituído ao fim.
Os dois arquivos não constituem uma publicação atômica conjunta. Reinicie as
sessões da API após incluir os datasets para registrar as novas tabelas DataFusion.
Não há materialização em banco nem mudança no schema dos BUs existentes.

## Validação e limites

Carga de 2026 executada em 28/10: 29 Parquets novos, mantendo os três anteriores;
32 arquivos no metadado, sucesso e nenhuma pendência. As saídas agora têm 108.184
locais cadastrais e 671.539 observações. O histórico de 2026 cobre 95.100 locais
em cada turno (04/10 e 25/10), nas 27 UFs. A auditoria por chaves naturais contra
todos os brutos encontrou zero observações ausentes ou extras; os valores do
histórico de 2018/2020/2022 e todos os IDs anteriores foram preservados.
Todos os 779.723 registros das duas saídas validaram no core; Bloom filters
reaplicados com comparação integral dos valores. Uma sessão DataFusion nova
retornou 93.227 locais, 85.808 comparáveis e 85.674 desenháveis em Presidente,
primeiros turnos 2022→2026. Os 1.329 grupos sem cadastro preservam 1.571.210 votos;
a soma dos votos locais e sem cadastro confere com o total de 119.306.034.
Não foi executada uma nova auditoria dos CSVs de boletins nesta operação.
Relatório em [voting_locations_2026-10-28.json](../../../../docs/audits/voting_locations_2026-10-28.json).

Validação da implementação original (26/10):

```bash
PYTHONPATH=apps/turi/src:. POLARS_MAX_THREADS=2 uv run python -m unittest discover -s apps/turi/tests -p 'test_voting*.py' -v
```

Os testes cobrem ZIP com CSVs estaduais sem arquivo nacional, acentos,
normalização de layouts, sobreposição entre arquivos, escopo da identidade,
deduplicação de seções, histórico, divergências, coordenadas inválidas, clusters
ausentes/ambíguos, compatibilidade com o core e preservação das saídas em falha.
A suíte Turi completa passou com 48 testes, sendo 12 desta operação.

Carga real de 2018, 2020 e 2022: 100.799 IDs cadastrais e 481.339 observações,
com cobertura das 27 UFs. Comparação independente das chaves naturais contra os
brutos encontrou zero observações ausentes ou extras. Nenhum município ficou sem
IBGE; 82.745 observações resolveram cluster e 63.691 ficaram sem coordenadas TSE.
Todos os 582.138 registros das duas saídas validaram na entidade do core.
Uma sessão real DataFusion consultou as duas tabelas. Bloom filters foram
aplicados e auditados somente nos dois novos arquivos nesta execução.

A carga encontrou 1.262 observações com algum campo divergente: 1.258 envolveram
situação cadastral, e quatro envolveram nomes, endereços ou coordenadas de dois IDs
em 2022, em ambos os turnos. Esses campos ficaram nulos com indicação explícita.

Os arquivos históricos consultados foram regenerados pelo TSE em 2024: ano
eleitoral não comprova que o endereço/coordenada ficou congelado naquele ano.
Não foi auditada nesta etapa a cobertura dos votos ou o vínculo dos itens de BU
com o novo catálogo. Para esse vínculo, usar o município físico, zona e local do
BU, e obter data/turno pelo contexto eleitoral do item. Consultas históricas devem
selecionar a observação correspondente e preservar votos sem localização.

Contagens por ano/turno/UF, hashes, divergências e auditoria em
[voting_locations_2026-10-26.json](../../../../docs/audits/voting_locations_2026-10-26.json).
