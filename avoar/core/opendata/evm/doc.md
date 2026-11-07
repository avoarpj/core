# Urnas, boletins e itens de boletim

Os produtores estão em `apps/turi/src/scripts/operations/evm/`. Os contratos
atuais permanecem em `domain.py`; esta nota documenta a execução de ETL e não
declara que todos os Parquets locais foram regenerados.

## Identidade e localidade

`EvmDataScript` produz uma urna por `NR_URNA_EFETIVADA`. O ID continua sendo o
hash com `NUMERIC_HASH_SEED` do número de série original. A projeção da coluna
de série ocorre antes da deduplicação para não materializar colunas alheias.

`EvmBulletinDataScript` identifica o boletim físico pelo hash de `urna_id`,
`hash_flashcard`, `hash_dados_carga_1` e `hash_dados_carga_2`. Cargo, eleição e
município eleitoral não pertencem a essa identidade. Um mesmo boletim contém
votos de múltiplos cargos/circunscrições.

O município IBGE é derivado do mapa TSE. O mapa é validado antes do join grande:
uma chave TSE não nula não pode ter dois destinos distintos. Repetições do mesmo
par são deduplicadas; chaves nulas não correspondem a municípios. Ao consolidar
boletins por ID, um único IBGE não nulo é preservado e conflitos ficam nulos.

Os itens mantêm sua identificação, tipos de voto e vínculos eleitorais existentes.
A primeira mudança de deduplicação não alterava seu produtor. Após o incidente
de consumo na carga completa, os itens passaram a processar uma fonte por vez,
com lookups previamente validados e sort externo DataFusion. Multiplicidades e
filtros de votos foram preservados; tipos são alinhados ao schema global antes
de gerar IDs, inclusive quando layouts históricos divergem.

## Deduplicação em disco (2026-10-27)

Urnas usam `lf = diskful_unique(lf, "NR_URNA_EFETIVADA")`. Boletins usam
`lf = diskful_unique(lf)` por arquivo após normalizar/projetar metadados, e
deduplicam novamente por `id` na consolidação global. As operações seguintes
continuam sendo cadeias Polars. A sessão por `process_data` remove temporários
somente depois do sink final; falhas não retêm os arquivos de índice.

O índice usa marcadores vazios SHA-256 e chaves originais separadas para tratar
colisões. DataFusion lê batches Arrow; não há materialização em banco para Fons.
No Polars 1.38, validação de join causa fallback em memória: valida-se o mapa
pequeno separadamente e a unicidade dos dois lados do join final já decorre da
deduplicação e do agrupamento. As ordenações finais existentes foram preservadas.

Uso, configurações, ciclo de vida, limites e medidas estão em
[docs/turi_diskful_unique.md](../../../../docs/turi_diskful_unique.md).
Testes dos produtores reais verificam IDs/valores, conflitos de município,
ordenação e limpeza. Testes maiores usam saídas temporárias, sem substituir os
Parquets publicados nem atualizar metadados dos scripts.

## Itens de boletim e carga completa

Execução do runner, proteção de publicação, auditorias de linhas/votos
e limites da validação estão em
[docs/turi_bulletin_items.md](../../../../docs/turi_bulletin_items.md).
