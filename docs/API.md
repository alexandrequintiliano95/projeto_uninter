# Contrato da API

Base local: `http://127.0.0.1:8000`.

Autenticação protegida usa `Authorization: Bearer <token>`. No Swagger (`/docs`), faça `POST /auth/login`, copie o `access_token` e cole-o em **Authorize**.

### Formato de erro

Todos os erros (regra de negócio, validação, rota inexistente e falha interna) usam o mesmo JSON:

```json
{
  "error": "DADOS_INVALIDOS",
  "message": "Um ou mais campos da requisição são inválidos.",
  "details": [{"field": "itens.0.quantidade", "message": "Input should be greater than 0"}],
  "timestamp": "2026-11-23T18:16:23Z",
  "path": "/pedidos"
}
```

- `details` é uma lista. Fica vazia em erros de regra de negócio e traz um item por campo em erros de validação (`422`).
- `timestamp` está em UTC (ISO 8601) e `path` é o caminho chamado.
- Códigos genéricos: `DADOS_INVALIDOS` (`422`), `RECURSO_NAO_ENCONTRADO` (`404` de rota), `METODO_NAO_PERMITIDO` (`405`) e `ERRO_INTERNO` (`500`, sem expor detalhes internos). Os demais códigos estão descritos em cada endpoint.

## Endpoints públicos

### GET `/health`

Verifica se a aplicação está ativa.

Resposta `200`:

```json
{"status":"ok"}
```

### POST `/auth/login`

Autentica um usuário. Perfis disponíveis: `CLIENTE`, `ATENDENTE`, `COZINHA` e `GERENTE`.

Request:

```json
{"email":"cliente@raizes.local","senha":"Cliente@123"}
```

Resposta `200`:

```json
{
  "access_token":"<jwt>",
  "token_type":"Bearer",
  "expires_in":3600,
  "user_id":1,
  "perfil":"CLIENTE"
}
```

Erros: `401` para credencial inválida e `422` para corpo inválido.

### GET `/unidades`

Lista unidades ativas. Não exige token.

Resposta `200`:

```json
[{"id":1,"nome":"Raízes Recife Centro","cidade":"Recife","uf":"PE"}]
```

### GET `/unidades/{unidade_id}/cardapio`

Lista o cardápio ativo da unidade. Query params: `page` inicia em 1 e `limit` varia de 1 a 100.

Resposta `200`:

```json
[
  {
    "produto_id":1,
    "nome":"Tapioca de Carne de Sol",
    "descricao":"Tapioca recheada com carne de sol",
    "preco_centavos":1890,
    "saldo_disponivel":20
  }
]
```

Erro: `404` quando a unidade não existe ou está inativa.

## Endpoints protegidos

### POST `/pedidos`

Cria um pedido e reserva o estoque por 15 minutos. `canal_pedido` aceita `APP`, `WEB`, `PICKUP`, `BALCAO` ou `TOTEM`. Cliente só pode usar `APP`, `WEB` ou `PICKUP`. Atendente e gerente da própria unidade podem usar `BALCAO`, `TOTEM` ou `PICKUP`. Os itens da resposta trazem em `produto_id` o ID do produto do catálogo.

Request:

```json
{
  "unidade_id":1,
  "canal_pedido":"APP",
  "itens":[{"produto_id":1,"quantidade":1}]
}
```

Resposta `201`:

```json
{
  "id":2,
  "unidade_id":1,
  "cliente_id":1,
  "canal_pedido":"APP",
  "status":"AGUARDANDO_PAGAMENTO",
  "total_centavos":1890,
  "motivo_cancelamento":null,
  "expira_em":"2026-11-14T15:00:00Z",
  "itens":[{"produto_id":1,"nome":"Tapioca de Carne de Sol","quantidade":1,"preco_unitario_centavos":1890}]
}
```

Erros: `401`, `403`, `404`, `409` para estoque insuficiente ou `422` para canal, quantidade ou itens inválidos.

### GET `/pedidos/{pedido_id}`

Consulta o próprio pedido ou um pedido da unidade do funcionário autenticado. A consulta também libera reservas vencidas.

Erros: `401`, `404` quando não pertence ao escopo do usuário.

### GET `/pedidos`

Lista pedidos do cliente autenticado ou da unidade do funcionário autenticado. Query params:

- `canalPedido`: `APP`, `WEB`, `PICKUP`, `BALCAO` ou `TOTEM`.
- `status`: `AGUARDANDO_PAGAMENTO`, `CONFIRMADO`, `EM_PREPARO`, `PRONTO`, `ENTREGUE` ou `CANCELADO`.
- `page` (a partir de 1) e `limit` (1 a 100).

Exemplo: `GET /pedidos?canalPedido=TOTEM&status=CONFIRMADO`.

Erros: `401` e `422` para filtro com valor desconhecido ou paginação inválida.

### POST `/pedidos/{pedido_id}/pagamentos/mock`

Registra o resultado simulado do pagamento. Body:

```json
{"resultado":"APROVADO"}
```

`APROVADO` muda o pedido para `CONFIRMADO` e consome a reserva. `RECUSADO` muda o pedido para `CANCELADO` e devolve a reserva. Uma segunda chamada com resultado diferente retorna `409`.

Cliente, atendente e gerente podem registrar o pagamento. A cozinha recebe `403`, inclusive ao repetir um pagamento já registrado.

Erros: `401`, `403` para perfil sem permissão, `404`, `409` para pedido fora do estado de pagamento ou resultado imutável e `422` para resultado inválido.

### PATCH `/pedidos/{pedido_id}/status`

Atualiza uma etapa do preparo ou da entrega. Body:

```json
{"status":"CONFIRMADO"}
```

Transições aceitas: `CONFIRMADO` para `EM_PREPARO` pela cozinha ou gerente, `EM_PREPARO` para `PRONTO` pela cozinha ou gerente, e `PRONTO` para `ENTREGUE` pelo atendente ou gerente.

Erros: `403` (`PERFIL_SEM_PERMISSAO`) quando o perfil não pode fazer aquela transição, como cliente alterando status ou cozinha marcando entregue; `404` para pedido fora do escopo; `409` (`TRANSICAO_INVALIDA`) quando o pedido não está no status informado ou a transição não existe.

### GET `/me/consentimentos`

Lista o último evento de consentimento do cliente autenticado por finalidade.

### POST `/me/consentimentos`

Registra concessão ou revogação de consentimento. A compra não depende desse registro.

Request:

```json
{"finalidade":"FIDELIDADE","concedido":true,"versao_termo":"v1"}
```

Erros: `401`, `403` para funcionário e `422` para finalidade inválida.

### GET `/auditoria`

Lista até 100 ações da própria unidade. Disponível apenas para gerente. Senhas, tokens e e-mails não são retornados.

Erro: `403` para outros perfis.

## Fluxo principal reproduzido

1. Fazer login como cliente.
2. Consultar `/unidades/1/cardapio`.
3. Criar pedido em `/pedidos`.
4. Aprovar ou recusar em `/pedidos/{id}/pagamentos/mock`.
5. Fazer login como cozinha e marcar `CONFIRMADO` para avançar a `EM_PREPARO`.
6. Continuar com `PRONTO` e `ENTREGUE` usando os perfis permitidos.

O contrato acima descreve somente endpoints existentes no código. Fidelidade, promoções, cadastro de equipe e relatórios continuam como evolução conceitual.
