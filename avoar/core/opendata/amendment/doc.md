# Emenda parlamentar

Estado em 2026-11-07: os modelos básicos permanecem neste domínio. DTOs,
agregações de resposta e consultas DataFusion pertencem ao Fons, em
`apps/fons/dto/amendment.py` e `apps/fons/infra/opendata`. Não há materialização
nem dependência DuckDB. Nomes ingleses e medições antigas no texto abaixo são
registro histórico; confira os campos atuais em `domain.py` e os contratos HTTP
em `docs/data_product_architecture.md`.

Esta entidade representa os dados de uma emenda parlamentar dentro do Avoar.

> **Significado institucional**: Emenda parlamentar é uma parcela do orçamento público federal que deputados e senadores têm o direito de indicar para destinar a estados, municípios ou entidades. Por meio delas, os congressistas influenciam o direcionamento dos recursos da União, podendo priorizar investimentos em áreas como saúde, educação e infraestrutura.

As emendas são dividas em vários tipos:

**Amendment**: O registro que marca a existência da emenda parlamentar

| Propriedade                                   | Descrição |
| ---------------- | --------------------------------------------- |
| id                               | ID-Avoar da emenda parlamentar                                                             |
| amendment_number                 | Identificador da emenda parlamentar no GOV                                                 |
| year                             | Ano em que a emenda parlamentar foi destinada                                              |

**Amendment Authorship**: Autoria da emenda parlamentar.

| Propriedade                                              | Descrição |
| --------------- | -------------------------------------------------------- |
| amendment_id                   | ID-Avoar da emenda parlamentar                                                                                   |
| authorship_type                | Tipo de autoria da emenda parlamentar (ENUM)                                                                     |
| mandate_id                     | ID-Avoar do mandato que destinou a emenda, se individual                                                         |
| authorship_name                | Nome do autor que aparece no sistema do GOV                                                                      |

**AmendmentResource**: Recurso da emenda parlamentar, é o registro da sua aplicação, informando para onde foi, suas categorias e valores.

| Propriedade                                                                                                 | Descrição |
| ----------------- | ----------------------------------------------------------------------------------------------------------- |
| amendment_id                       | ID-Avoar da emenda parlamentar                                                                                                                                                                                         |
| place_code                         | Código do local onde foi destinada. Código IBGE para municipios, sigla UF para estados e "BR" para nacional                                                                                                            |
| function_code                      | Código da função                                                                                                                                                                                                       |
| sub_function_code                  | Código da subfunção                                                                                                                                                                                                    |
| program_code                       | Código do programa                                                                                                                                                                                                     |
| action_code                        | Código da ação                                                                                                                                                                                                         |
| budget_plan_code                   | Código do plano orçamentário                                                                                                                                                                                           |
| budget_plan_name                   | Nome do plano orçamentário                                                                                                                                                                                             |
| amount_committed                   | Valor empenhado                                                                                                                                                                                                        |
| amount_settled                     | Valor liquidado                                                                                                                                                                                                        |
| amount_paid                        | Valor pago                                                                                                                                                                                                             |
| rap_recorded                       | Restos a pagar inscritos                                                                                                                                                                                               |
| rap_cancelled                      | Restos a pagar cancelados                                                                                                                                                                                              |
| rap_paid                           | Restos a pagar pagos                                                                                                                                                                                                   |

**AmendmentItem**: Um item da emenda, é o tipo normalizado para os códigos de função, subfunção, programa e ação.

O plano orçamentário não é normalizado porque seus IDs são inconsistentes.

| Propriedade    | Descrição |
| ----------- | -------------- |
| id                     | Código do item               |
| value                  | Nome do item                 |
| type                   | Tipo do item                 |

**AmendmentAgreement**: Os convênios criados para custeamento das emendas parlamentares.

PS: várias emendas podem custear um convênio, então, a relação escolhida entre os dois é *many-to-many*. A modelagem dessa é parte da infra. O core cuida somente do tipo de dado bruto.

| Propriedade                                                             | Descrição |
| ---------------- | ----------------------------------------------------------------------- |
| id                               | ID-Avoar do convênio                                                                                                                           |
| agreement_number                 | Número do convênio que aparece no GOV                                                                                                          |
| publication_date                 | Data de publicação do convênio                                                                                                                 |
| grantee                          | Nome do convenente                                                                                                                             |
| purpose                          | Objeto do convênio (em poucas palavras, exatamente o serviço executado)                                                                        |
| value                            | Valor do convênio                                                                                                                              |

O valor do convênio é uma **estimativa** calculada pelo convenente.

## Listagem de emendas por mandato

`GET /opendata/mandates/{mandate_id}/amendments` retorna
`EmendaParlamentarDetalhada[]`. O vínculo é `opendata_amendment_authorship`
com o mandato. Cada emenda traz `autorias`, `recursos`, `fornecedores` e
`convenios` como listas, inclusive quando vazias. Cada recurso inclui os itens
normalizados `funcao`, `subfuncao`, `programa` e `acao` quando encontrados em
`opendata_amendment_item`; os códigos brutos e valores permanecem no recurso.

Cada entrada de `fornecedores` conserva `fornecedor_id`, `tipo_documento` e
`valor`, além da chave `fornecedor`. Para CNPJ, o fornecedor usa o
estabelecimento da Receita Federal e seus nomes fantasia e razão social; para
os demais documentos usa `opendata_services_supplier` e seus nomes coletados.
Se a entidade referenciada não estiver carregada, `fornecedor` é nulo e o
vínculo financeiro permanece. Os convênios são carregados pelo vínculo
`opendata_amendment_to_agreement`.

Os filtros opcionais repetíveis `ano`, `tipo_autoria` e `fornecedor_id` usam OR
dentro de cada filtro e AND entre filtros. `tipo_autoria` considera a autoria
do mandato solicitado. Paginação keyset usa `limit` (1 a 1000), `order`
(`asc` ou `desc`), `pull_by=id` e `pull_after` (ID unsigned de 64 bits,
exclusivo). O padrão é `limit=1000&order=asc&pull_by=id`. Mandato inexistente
retorna 404; sem emendas compatíveis retorna `[]`. IDs e valores decimais são
strings no JSON.

A implementação pagina emendas antes de consultar relações em lotes, na mesma
transação. Isso preserva o limite quando há vários recursos ou fornecedores.
Para fornecedores CNPJ, consulta primeiro somente os estabelecimentos da
página e depois as empresas correspondentes pelos seus IDs. Uma junção direta
entre as duas tabelas completas causou latência alta no banco local.
`tests/test_mandate_amendments.py` cobre o endpoint HTTP com o core montado,
relações, filtros, paginação, OpenAPI e equivalência dos formatos de retorno.

## Ordenação cronológica no portal

A listagem por mandato também aceita `pull_by=ano`, ordenando por ano e ID
na mesma direção. O cursor composto `pull_after=ano|id` é exclusivo e validado;
`pull_by=id` mantém o contrato anterior. Ano não informa a data de pagamento:
a apresentação usa explicitamente o ano orçamentário da emenda. O Rostra
consulta páginas de 10 registros em ordem decrescente e pode recolher a lista.

Ordenação física dos dumps corrigida em 2026-10-14: autoria agrupa mandato/emenda;
recursos, pagamentos e vínculos de convênios agrupam emenda; convênios ordenam ID,
e itens tipo/ID. As consultas continuam declarando ORDER BY quando necessário.
Reordenação não deduplica nem modifica autoria ou valores. Ver
[ordenação e auditoria](../../../../docs/parquet_ordering.md).
