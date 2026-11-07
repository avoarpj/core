# Órgão

Representa a instituição associada a eleições, legislaturas e mandatos. O catálogo
`opendata_organ` substitui `opendata_legislative_house`, permitindo representar
instituições de outros poderes, além das casas legislativas.

| Campo | Descrição |
| --- | --- |
| `id` | Identificador textual do órgão |
| `nome` | Nome completo do órgão |

O produtor estático é `apps/turi/src/scripts/operations/organs/organs.py` e grava
`parquet_dumps/opendata/opendata_organ/static.parquet`, ordenado por ID:

| ID | Nome |
| --- | --- |
| `cd` | Câmara dos Deputados |
| `gov` | Governo Federal |
| `sf` | Senado Federal |

As referências usam `orgao_id`. A proveniência dos nomes de fornecedores usa
`coletado_de_orgao_id`; os nomes embutidos nos rankings usam `orgao_nome`.
Os IDs anteriores de pessoas, eleições, legislaturas e mandatos não dependem
dessa renomeação e são preservados.

A API expõe `GET /opendata/organ/`, `GET /opendata/organ/{id}` e
`GET /opendata/organ/{id}/legislatures`. Órgão existente sem legislaturas retorna
`[]`; órgão inexistente retorna 404. A listagem/pesquisa de pessoas aceita
`orgao_id` como parâmetro. O cadastro de `gov` não cria mandatos presidenciais
nem associa automaticamente eleições antigas ao novo órgão.

Para migrar dumps locais antigos, sem executar novamente todos os produtores:

```bash
PYTHONPATH=apps/turi/src:. uv run python -m scripts.maintenance.migrate_organs \
  --report docs/audits/organ_schema_migration.json
```

A manutenção descobre as colunas dos Parquets finais, renomeia as referências e
a pasta do catálogo. Confere todos os valores, ordem, schema, metadados e grupos
antes de cada substituição atômica; mantém compressão e cobertura Bloom. É
idempotente. Depois, execute o produtor estático para incluir `gov`.

Reinicie Fons após a migração para registrar os novos schemas e o catálogo;
reinicie Rostra para consumir os contratos novos. IndexedDB usa a versão 2.
Respostas Redis antigas podem persistir até o TTL (cinco minutos por padrão);
em publicação coordenada, configure um namespace novo nos dois serviços.

As migrations SQL em `avoar/infra/database/migrations` e auditorias anteriores
são registros históricos. A arquitetura atual consulta os Parquets diretamente
com DataFusion e não aplica essas migrations para registrar tabelas.
