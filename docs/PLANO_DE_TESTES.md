# Plano de testes

> Nota: elaborado com apoio de IA (Claude Code) e revisado pelo autor.

Este plano lista os cenários que comprovam as regras da API, cada um com a evidência que o executa. Há duas formas de execução que se complementam:

- **pytest** (`tests/`): testes automatizados que sobem a API em memória sobre um banco SQLite temporário, criado do zero para cada teste. Não usam nem alteram o `raizes.db`.
- **Postman** (`postman/raizes-backend.postman_collection.json`): 60 requisições em 7 pastas, com asserções em todas. Rodam contra a API em execução, na ordem das pastas.

## Pré-condições gerais

- Banco migrado e populado: `alembic upgrade head` e `python seed.py`.
- Usuários do seed:

| Perfil | E-mail | Senha |
| --- | --- | --- |
| Cliente | `cliente@raizes.local` | `Cliente@123` |
| Atendente (Recife) | `atendente.recife@raizes.local` | `Atendente@123` |
| Cozinha (Recife) | `cozinha.recife@raizes.local` | `Cozinha@123` |
| Gerente (Recife) | `gerente.recife@raizes.local` | `Gerente@123` |
| Gerente (Caruaru) | `gerente.caruaru@raizes.local` | `Gerente@123` |

- Preços do seed na unidade 1 (Recife Centro): tapioca R$ 18,90 (saldo 20), cuscuz R$ 15,90 (saldo 15) e suco R$ 8,90 (saldo 30).

## Cenários positivos

| ID | Cenário | Pré-condição | Entrada | Saída esperada | Evidência |
| --- | --- | --- | --- | --- | --- |
| CT01 | Login válido | Seed aplicado | `POST /auth/login` com o cliente | `200`, `token_type` `Bearer`, perfil `CLIENTE` | Postman A02; pytest `test_login_and_missing_token` |
| CT02 | Cadastro de cliente | E-mail ainda não cadastrado | `POST /auth/cadastro` com nome, e-mail, senha forte e `aceite_termos: true` | `201`, perfil `CLIENTE`, sem senha na resposta; login funciona depois | Postman A08; pytest `test_client_signs_up_and_can_order` |
| CT03 | Consulta do cardápio | Nenhuma (rota pública) | `GET /unidades/1/cardapio` | `200`, tapioca com `preco_centavos` 1890 | Postman C02; pytest `test_health_and_public_catalog` |
| CT04 | Criação de pedido | Cliente autenticado; estoque disponível | `POST /pedidos` com `unidadeId` 1, `canalPedido` `APP` e 1 tapioca | `201`, status `AGUARDANDO_PAGAMENTO`, total 1890, `produto_id` 1; saldo livre cai 1 | Postman P02; pytest `test_order_items_return_catalog_product_id`, `test_client_cancels_own_pending_order` |
| CT05 | Pagamento aprovado | Pedido aguardando pagamento | `POST /pedidos/{id}/pagamentos/mock` com `APROVADO` | `200`, `pedido_status` `CONFIRMADO` | Postman P10; pytest `test_kitchen_advances_paid_order` |
| CT06 | Preparo e entrega | Pedido confirmado | `PATCH /pedidos/{id}/status` com `EM_PREPARO` e `PRONTO` (cozinha) e `ENTREGUE` (atendente) | `200` em cada etapa, status final `ENTREGUE` | Postman P12, P14, P16; pytest `test_order_goes_from_kitchen_to_delivery` |
| CT07 | Listagem com filtros | Pedidos de canais e status diferentes | `GET /pedidos?canalPedido=APP&status=ENTREGUE` | `200` só com pedidos `APP` entregues | Postman P17; pytest `test_list_orders_filters_by_canal_pedido`, `test_list_orders_filters_by_status` |
| CT08 | Cancelamento antes do pagamento | Pedido aguardando pagamento | `POST /pedidos/{id}/cancelamento` | `200`, `CANCELADO` com motivo `SOLICITADO`; reserva devolvida | Postman X02; pytest `test_client_cancels_own_pending_order` |
| CT09 | Pagamento recusado | Pedido aguardando pagamento | Pagamento mock com `RECUSADO` | `200`, pedido `CANCELADO` (`PAGAMENTO_RECUSADO`); reserva devolvida | Postman X05; pytest `test_create_order_and_reject_payment` |
| CT10 | Entrada de estoque | Gerente da unidade autenticado | `POST /unidades/1/estoque/movimentacoes` com `ENTRADA` de 10 e motivo | `201`, saldo livre aumenta 10; histórico e auditoria registrados | Postman E01, E05; pytest `test_manager_registers_stock_entry` |
| CT11 | Acúmulo e resgate de pontos | Consentimento `FIDELIDADE` concedido | Pedido de R$ 113,40 pago; depois pedido de R$ 37,80 com `pontos_resgatados: 100` | 113 pontos creditados; desconto de R$ 5,00 (total R$ 32,80); pontos devolvidos se o pedido for cancelado | Postman F01 a F09; pytest `test_points_become_discount_and_paid_value_earns_points`, `test_cancelled_order_returns_redeemed_points` |
| CT12 | Auditoria do gerente e registro de acesso | Operações feitas na unidade; atendente consultou um pedido de cliente | `GET /auditoria` com o gerente | `200` com `PEDIDO_CRIADO`, `PAGAMENTO_MOCK`, `STATUS_ATUALIZADO`, `ESTOQUE_AJUSTADO`, o acesso `DADOS_CLIENTE_CONSULTADOS` do atendente e a consulta anterior `AUDITORIA_CONSULTADA`, sem e-mail, senha ou token | Postman U01, U04, U05; pytest `test_client_consent_and_manager_audit`, `test_staff_reading_a_client_order_is_audited`, `test_audit_consultation_is_itself_audited` |

## Cenários negativos

| ID | Cenário | Pré-condição | Entrada | Saída esperada | Evidência |
| --- | --- | --- | --- | --- | --- |
| CT13 | Acesso sem token | Nenhuma | `GET /pedidos` sem `Authorization` | `401` `NAO_AUTENTICADO`, no formato de erro padrão | Postman P01; pytest `test_domain_error_uses_standard_format` |
| CT14 | Senha errada | Seed aplicado | `POST /auth/login` com senha incorreta | `401` `CREDENCIAIS_INVALIDAS` | Postman A07; pytest `test_login_with_wrong_password_is_rejected` |
| CT15 | E-mail já cadastrado | Cliente do seed existe | `POST /auth/cadastro` com `cliente@raizes.local` | `409` `EMAIL_JA_CADASTRADO` | Postman A09; pytest `test_signup_rejects_email_already_registered` |
| CT16 | Canal inválido | Cliente autenticado | Pedido com `canalPedido: "INVALIDO"` | `422` `DADOS_INVALIDOS`, campo `canalPedido` em `details` | Postman P04; pytest `test_invalid_channel_and_invalid_quantity` |
| CT17 | Canal não permitido ao perfil | Cliente autenticado | Pedido com canal `BALCAO` | `403` `CANAL_NAO_PERMITIDO` | Postman P05; pytest `test_client_cannot_create_balcao_order` |
| CT18 | Estoque insuficiente no pedido | Saldo livre menor que a quantidade | Pedido com quantidade acima do saldo | `409` `ESTOQUE_INSUFICIENTE`, sem reservar nada | Postman P06; pytest `test_order_beyond_stock_is_rejected_without_reserving` |
| CT19 | Pedido de outra unidade | Pedido criado em Recife | `GET /pedidos/{id}` com o gerente de Caruaru | `404` `PEDIDO_NAO_ENCONTRADO` | Postman P07; pytest `test_staff_cancels_only_orders_of_own_unit`, `test_acesso_ao_pedido` |
| CT20 | Cozinha tenta pagar | Pedido aguardando pagamento | Pagamento mock com o token da cozinha | `403` `PERFIL_SEM_PERMISSAO`; pedido continua aguardando | Postman P08; pytest `test_kitchen_cannot_pay_order` |
| CT21 | Falha do provedor de pagamento | Pedido aguardando pagamento | Pagamento mock com `FALHA` | `503` `PAGAMENTO_INDISPONIVEL`; nenhum pagamento gravado; pedido pode ser pago depois | Postman P09; pytest `test_payment_failure_returns_503_and_keeps_order_waiting` |
| CT22 | Troca do resultado do pagamento | Pedido já aprovado | Pagamento mock com `RECUSADO` | `409` `PAGAMENTO_IMUTAVEL` | Postman P11; pytest `test_payment_result_cannot_be_changed` |
| CT23 | Pular etapa de status | Pedido `EM_PREPARO` | `PATCH` com `ENTREGUE` (gerente) | `409` `TRANSICAO_INVALIDA` | Postman P13; pytest `test_skipping_a_step_is_conflict` |
| CT24 | Perfil sem permissão na entrega | Pedido `PRONTO` | `PATCH` com `ENTREGUE` pela cozinha | `403` `PERFIL_SEM_PERMISSAO`; pedido continua `PRONTO` | Postman P15; pytest `test_kitchen_cannot_mark_order_delivered` |
| CT25 | Cancelar pedido pago | Pedido já pago (confirmado ou em etapa seguinte) | `POST /pedidos/{id}/cancelamento` | `409` `PEDIDO_NAO_CANCELAVEL` | Postman X03; pytest `test_paid_order_cannot_be_cancelled` |
| CT26 | Saída de estoque acima do saldo livre | Itens reservados em pedido | `SAIDA` maior que o saldo livre | `409` `ESTOQUE_INSUFICIENTE`; reservas intactas | Postman E02; pytest `test_stock_exit_never_takes_reserved_items` |
| CT27 | Ajuste de estoque sem permissão | Atendente ou gerente de outra unidade | `POST /unidades/1/estoque/movimentacoes` | `403` `PERFIL_SEM_PERMISSAO` ou `UNIDADE_NAO_PERMITIDA` | Postman E03, E04; pytest `test_only_manager_of_the_unit_moves_stock` |
| CT28 | Resgate fora das regras | Cliente com pontos | `pontosResgatados` 150, acima do saldo ou acima de 50% | `422` `DADOS_INVALIDOS`, `409` `SALDO_PONTOS_INSUFICIENTE` ou `422` `DESCONTO_ACIMA_DO_LIMITE` | Postman F07; pytest `test_redemption_limits` |
| CT29 | Auditoria por cliente | Cliente autenticado | `GET /auditoria` | `403` `PERFIL_SEM_PERMISSAO` | Postman U02; pytest `test_client_consent_and_manager_audit` |
| CT30 | Campo obrigatório ausente | Cliente autenticado | Pedido sem `canalPedido` | `422` `DADOS_INVALIDOS`, campo `canalPedido` em `details` | Postman P19; pytest `test_order_without_channel_points_to_roteiro_field_name` |
| CT31 | Quantidade negativa | Cliente autenticado | Pedido com `quantidade: -1` | `422` `DADOS_INVALIDOS`, campo `itens.0.quantidade` em `details` | Postman P20; pytest `test_negative_quantity_points_to_the_item_field` |
| CT32 | E-mail em formato inválido | Nenhuma (rota pública) | `POST /auth/cadastro` com `email: "nao-e-email"` | `422` `DADOS_INVALIDOS`, campo `email` em `details` | Postman A11; pytest `test_signup_validates_name_and_email_format` |
| CT33 | Pedido com produto inexistente | Cliente autenticado | Pedido com `produtoId` 999 | `404` `PRODUTO_INDISPONIVEL`, sem reservar nada | Postman P21; pytest `test_product_without_offer_in_the_unit_is_unavailable`, `test_inactive_product_is_unavailable` |

Toda resposta de erro também é conferida por um teste geral da coleção Postman: ela precisa ter exatamente os campos `error`, `message`, `details`, `timestamp` e `path`. Na execução registrada, esse teste rodou em 26 respostas de erro.

## Como executar

### pytest

Na raiz do projeto, com o ambiente virtual ativado (Linux, macOS ou Git Bash: `source .venv/bin/activate`; PowerShell: `.\.venv\Scripts\Activate.ps1`):

```bash
python -m pytest -q
```

O pytest cria um banco temporário próprio; não é preciso subir a API nem rodar o seed antes.

### Coleção Postman

1. Prepare o banco e suba a API:

   ```bash
   alembic upgrade head
   python seed.py
   uvicorn app.main:app
   ```

2. No Postman, importe `postman/raizes-backend.postman_collection.json` e execute a coleção inteira no **Collection Runner**, na ordem das pastas. A variável `baseUrl` já aponta para `http://127.0.0.1:8000`.

   Pela linha de comando, com o Newman (requer Node.js):

   ```bash
   npx newman run postman/raizes-backend.postman_collection.json
   ```

A coleção guarda os IDs criados em variáveis (`pedidoId`, `pedidoCanceladoId`, `movimentacaoId` e outros) e pode ser executada várias vezes sobre o mesmo banco.

## Resultado da última execução (23/11/2026)

| Execução | Resultado | Evidência |
| --- | --- | --- |
| pytest | 131 testes passaram, 0 falhas | [evidencias/pytest-execucao.txt](evidencias/pytest-execucao.txt) |
| Newman, 1ª execução (banco recém-criado) | 60 requisições, 150 asserções, 0 falhas | [evidencias/newman-execucao.txt](evidencias/newman-execucao.txt) |
| Newman, 2ª execução seguida (mesmo banco) | 60 requisições, 150 asserções, 0 falhas | Execução de conferência, não arquivada |

A execução do Newman usou a porta 8765 e um banco descartável, para não alterar o `raizes.db` local.
