# Contrato da API

> Nota: trechos alterados com apoio de IA (Claude Code) e revisados pelo autor.

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
- Códigos genéricos: `DADOS_INVALIDOS` (`422`), `RECURSO_NAO_ENCONTRADO` (`404` de rota), `METODO_NAO_PERMITIDO` (`405`), `ERRO_INTERNO` (`500`, sem expor detalhes internos) e `PAGAMENTO_INDISPONIVEL` (`503`, falha simulada do provedor de pagamento). Os demais códigos estão descritos em cada endpoint.

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

### POST `/auth/cadastro`

Cadastro público de cliente, sem token. Request:

```json
{
  "nome":"Maria das Dores",
  "email":"maria@exemplo.com",
  "senha":"Segura123",
  "aceite_termos":true,
  "aceita_fidelidade":false,
  "aceita_marketing":false
}
```

- A conta sempre nasce com perfil `CLIENTE` e sem unidade. Campos como `perfil` ou `unidade_id` enviados no corpo são ignorados.
- O e-mail é gravado em minúsculas e sem espaços nas pontas. A senha é guardada só como hash Argon2 e nunca volta nas respostas.
- `aceite_termos` precisa ser `true`. A auditoria registra `USUARIO_CADASTRADO` com a versão dos termos aceita (`v1`), sem guardar o e-mail.
- `aceita_fidelidade` e `aceita_marketing` são consentimentos opcionais e separados, `false` por padrão. Só geram evento em `/me/consentimentos` quando chegam como `true`.

Resposta `201`:

```json
{"id":6,"nome":"Maria das Dores","email":"maria@exemplo.com","perfil":"CLIENTE"}
```

Depois do cadastro, o login é feito normalmente em `POST /auth/login`.

Erros: `409` (`EMAIL_JA_CADASTRADO`); `422` (`TERMOS_NAO_ACEITOS`) quando `aceite_termos` é `false`; `422` (`SENHA_FRACA`) para senha fora de 8 a 128 caracteres ou sem letra e número; `422` (`DADOS_INVALIDOS`) para nome vazio ou com menos de 2 caracteres e e-mail em formato inválido.

### GET `/unidades`

Lista unidades ativas. Não exige token.

Resposta `200`:

```json
[{"id":1,"nome":"Raízes Recife Centro","cidade":"Recife","uf":"PE"}]
```

### GET `/unidades/{unidade_id}/cardapio`

Lista o cardápio ativo da unidade. Query params: `page` inicia em 1 e `limit` varia de 1 a 100. Antes de listar, a consulta libera as reservas de pedidos com prazo vencido, para que `saldo_disponivel` não apareça menor do que é.

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

Cria um pedido e reserva o estoque por 15 minutos. `canalPedido` aceita `APP`, `WEB`, `PICKUP`, `BALCAO` ou `TOTEM`. Cliente só pode usar `APP`, `WEB` ou `PICKUP`. Atendente e gerente da própria unidade podem usar `BALCAO`, `TOTEM` ou `PICKUP`. Os itens da resposta trazem em `produto_id` o ID do produto do catálogo.

O campo opcional `pontosResgatados` usa pontos de fidelidade como desconto. Ele aceita múltiplos de 100 (cada 100 pontos valem R$ 5,00), limitados ao saldo e a 50% do valor do pedido, e só vale para cliente com consentimento `FIDELIDADE` ativo. Os pontos saem do saldo na criação e voltam (`ESTORNO`) se o pedido for cancelado, recusado ou vencer. `total_centavos` é o valor a pagar, já com o desconto.

Request:

```json
{
  "unidadeId":1,
  "canalPedido":"APP",
  "itens":[{"produtoId":1,"quantidade":1}],
  "pontosResgatados":0
}
```

O corpo usa os nomes de campo do roteiro (`unidadeId`, `canalPedido`, `produtoId`, `pontosResgatados`). Os nomes internos (`unidade_id`, `canal_pedido`, `produto_id`, `pontos_resgatados`) também são aceitos, para compatibilidade. A resposta usa os nomes internos, como as demais rotas.

Resposta `201`:

```json
{
  "id":2,
  "unidade_id":1,
  "cliente_id":1,
  "canal_pedido":"APP",
  "status":"AGUARDANDO_PAGAMENTO",
  "total_centavos":1890,
  "desconto_centavos":0,
  "pontos_resgatados":0,
  "motivo_cancelamento":null,
  "expira_em":"2026-11-14T15:00:00Z",
  "itens":[{"produto_id":1,"nome":"Tapioca de Carne de Sol","quantidade":1,"preco_unitario_centavos":1890}]
}
```

Erros: `401`, `403`, `404` para unidade inexistente ou produto inexistente, desativado ou sem oferta ativa na unidade (`PRODUTO_INDISPONIVEL`), `409` para estoque insuficiente, saldo de pontos insuficiente (`SALDO_PONTOS_INSUFICIENTE`) ou consentimento de fidelidade inativo (`FIDELIDADE_INATIVA`), `403` (`PERFIL_SEM_PERMISSAO`) quando um funcionário tenta resgatar pontos, ou `422` para canal, quantidade, itens ou pontos inválidos (`pontos_resgatados` fora de múltiplos de 100 ou `DESCONTO_ACIMA_DO_LIMITE`).

### GET `/pedidos/{pedido_id}`

Consulta o próprio pedido ou um pedido da unidade do funcionário autenticado. A consulta também libera reservas vencidas.

Erros: `401`, `404` quando não pertence ao escopo do usuário.

### GET `/pedidos`

Lista pedidos do cliente autenticado ou da unidade do funcionário autenticado. A cozinha só vê pedidos já pagos (`CONFIRMADO`, `EM_PREPARO`, `PRONTO` e `ENTREGUE`); um pedido fora disso responde `404` também em `GET /pedidos/{pedido_id}`. Query params:

- `canalPedido`: `APP`, `WEB`, `PICKUP`, `BALCAO` ou `TOTEM`.
- `status`: `AGUARDANDO_PAGAMENTO`, `CONFIRMADO`, `EM_PREPARO`, `PRONTO`, `ENTREGUE` ou `CANCELADO`.
- `page` (a partir de 1) e `limit` (1 a 100).

Exemplo: `GET /pedidos?canalPedido=TOTEM&status=CONFIRMADO`.

Erros: `401` e `422` para filtro com valor desconhecido ou paginação inválida.

### POST `/pedidos/{pedido_id}/pagamentos/mock`

Simula o provedor de pagamento. Body:

```json
{"resultado":"APROVADO"}
```

| `resultado` | Efeito |
| --- | --- |
| `APROVADO` | Grava o pagamento, muda o pedido para `CONFIRMADO` e consome a reserva. Se o pedido é de um cliente com consentimento `FIDELIDADE` ativo, credita 1 ponto por real pago (arredondando para baixo). |
| `RECUSADO` | Grava o pagamento, muda o pedido para `CANCELADO` (`PAGAMENTO_RECUSADO`) e devolve a reserva. |
| `FALHA` | Simula o provedor fora do ar: responde `503` (`PAGAMENTO_INDISPONIVEL`), não grava pagamento e registra `PAGAMENTO_FALHA` na auditoria. O pedido continua `AGUARDANDO_PAGAMENTO`, com a reserva sujeita ao prazo, e pode ser pago depois. |

Repetir o mesmo resultado devolve o pagamento já gravado. Uma chamada com resultado diferente do gravado retorna `409` (`PAGAMENTO_IMUTAVEL`).

Cliente, atendente e gerente podem registrar o pagamento. A cozinha recebe `403`, inclusive ao repetir um pagamento já registrado.

Um pedido com prazo de reserva vencido é cancelado (`PRAZO_EXPIRADO`) e o pagamento é recusado com `409` (`PEDIDO_SEM_PAGAMENTO`).

Erros: `401`, `403` para perfil sem permissão, `404`, `409` para pedido fora do estado de pagamento (inclusive vencido ou cancelado) ou resultado imutável, `422` (`DADOS_INVALIDOS`) para `resultado` fora de `APROVADO`, `RECUSADO` ou `FALHA` e `503` (`PAGAMENTO_INDISPONIVEL`) para a falha simulada.

### POST `/pedidos/{pedido_id}/cancelamento`

Cancela o pedido antes do pagamento, sem body. O pedido passa a `CANCELADO` com `motivo_cancelamento` igual a `SOLICITADO`, a reserva volta ao saldo livre e a auditoria registra `PEDIDO_CANCELADO`. A resposta `200` traz o pedido atualizado.

- Cliente cancela os próprios pedidos. Atendente e gerente cancelam pedidos da própria unidade. A cozinha recebe `403`.
- Repetir o cancelamento devolve `200` com o pedido como está, sem devolver a reserva de novo nem gravar outra auditoria. Isso vale também para pedido cancelado por recusa ou por prazo vencido.
- Pedido já pago (`CONFIRMADO` em diante) não pode ser cancelado neste protótipo, porque não há estorno: retorna `409` (`PEDIDO_NAO_CANCELAVEL`).

Erros: `401`, `403` (`PERFIL_SEM_PERMISSAO`), `404` para pedido fora do escopo e `409` (`PEDIDO_NAO_CANCELAVEL`).

### PATCH `/pedidos/{pedido_id}/status`

Avança o pedido para a próxima etapa do preparo ou da entrega. O body informa o status de **destino**:

```json
{"status":"EM_PREPARO"}
```

| Destino | Status exigido no pedido | Perfis |
| --- | --- | --- |
| `EM_PREPARO` | `CONFIRMADO` | Cozinha ou gerente |
| `PRONTO` | `EM_PREPARO` | Cozinha ou gerente |
| `ENTREGUE` | `PRONTO` | Atendente ou gerente |

Repetir o status em que o pedido já está devolve `200` com o pedido como está, sem gravar nova auditoria. `CONFIRMADO` e `CANCELADO` não são aceitos nesta rota: dependem do pagamento, do cancelamento (`POST /pedidos/{pedido_id}/cancelamento`) ou da expiração.

Erros: `403` (`PERFIL_SEM_PERMISSAO`) quando o perfil não pode fazer aquela transição, como cliente alterando status ou cozinha marcando entregue; `404` para pedido fora do escopo; `409` (`TRANSICAO_INVALIDA`) quando o pedido não está no status exigido ou o destino não é aceito nesta rota; `422` para status desconhecido.

### POST `/unidades/{unidade_id}/estoque/movimentacoes`

Registra uma entrada ou saída manual de estoque. Disponível apenas para o gerente da própria unidade. Body:

```json
{"produto_id":1,"tipo":"ENTRADA","quantidade":10,"motivo":"Reposição do fornecedor"}
```

- `ENTRADA` soma `quantidade` ao saldo livre da oferta; `SAIDA` subtrai.
- A saída nunca retira itens reservados em pedidos: se `quantidade` passar do saldo livre, a resposta é `409` (`ESTOQUE_INSUFICIENTE`).
- Antes do ajuste, reservas vencidas da unidade voltam ao saldo livre.
- Cada movimentação fica na tabela `movimentacao_estoque` e também gera `ESTOQUE_AJUSTADO` na auditoria, com o saldo anterior e o novo.

Resposta `201`:

```json
{
  "id":1,
  "unidade_id":1,
  "produto_id":1,
  "tipo":"ENTRADA",
  "quantidade":10,
  "motivo":"Reposição do fornecedor",
  "saldo_livre_anterior":20,
  "saldo_livre_novo":30,
  "usuario_id":4,
  "criado_em":"2026-11-23T19:30:00Z"
}
```

Erros: `401`; `403` (`PERFIL_SEM_PERMISSAO`) para quem não é gerente e (`UNIDADE_NAO_PERMITIDA`) para gerente de outra unidade; `404` (`PRODUTO_INDISPONIVEL`) quando o produto não tem oferta na unidade; `409` (`ESTOQUE_INSUFICIENTE`); `422` para tipo desconhecido, quantidade menor que 1 ou motivo vazio ou com menos de 3 caracteres.

### GET `/unidades/{unidade_id}/estoque/movimentacoes`

Histórico de movimentações da unidade, da mais recente para a mais antiga. Disponível apenas para o gerente da própria unidade. Query params: `produtoId` (opcional, filtra um produto), `page` e `limit`.

Exemplo: `GET /unidades/1/estoque/movimentacoes?produtoId=1`.

Erros: `401`, `403` e `422` para parâmetros inválidos.

### GET `/me/fidelidade`

Saldo e extrato de pontos do cliente autenticado. Funcionários recebem `403`.

Resposta `200`:

```json
{
  "saldo_pontos":45,
  "consentimento_ativo":true,
  "regras":{"pontos_por_real_pago":1,"pontos_por_resgate":100,"desconto_por_resgate_centavos":500,"desconto_maximo_percentual":50},
  "extrato":[
    {"id":3,"pedido_id":2,"tipo":"CREDITO","pontos":32,"criado_em":"2026-11-23T20:10:00Z"},
    {"id":2,"pedido_id":2,"tipo":"DEBITO","pontos":100,"criado_em":"2026-11-23T20:09:00Z"},
    {"id":1,"pedido_id":1,"tipo":"CREDITO","pontos":113,"criado_em":"2026-11-23T20:08:00Z"}
  ]
}
```

- `CREDITO`: pontos ganhos em pedido pago. `DEBITO`: pontos usados como desconto. `ESTORNO`: pontos devolvidos quando o pedido com desconto não foi pago.
- O saldo é a soma de créditos e estornos menos os débitos. O extrato mostra os últimos 100 movimentos, do mais recente para o mais antigo.
- Sem consentimento `FIDELIDADE` ativo, o cliente compra normalmente, mas não acumula nem resgata. Ao revogar, o saldo fica congelado e volta a valer com um novo consentimento.

### GET `/me/consentimentos`

Lista o último evento de consentimento do cliente autenticado por finalidade.

### POST `/me/consentimentos`

Registra concessão ou revogação de consentimento. A compra não depende desse registro.

Request:

```json
{"finalidade":"FIDELIDADE","concedido":true,"versao_termo":"v1"}
```

Erros: `401`, `403` para funcionário e `422` (`DADOS_INVALIDOS`) para `finalidade` diferente de `FIDELIDADE` ou `MARKETING`.

### GET `/auditoria`

Lista até 100 ações da própria unidade. Disponível apenas para gerente. Senhas, tokens e e-mails não são retornados.

Erro: `403` para outros perfis.

## Fluxo principal reproduzido

1. Fazer login como cliente.
2. Consultar `/unidades/1/cardapio`.
3. Criar pedido em `/pedidos`.
4. Aprovar ou recusar em `/pedidos/{id}/pagamentos/mock`.
5. Fazer login como cozinha e enviar `{"status":"EM_PREPARO"}` e depois `{"status":"PRONTO"}`.
6. Fazer login como atendente e enviar `{"status":"ENTREGUE"}`.

O contrato acima descreve somente endpoints existentes no código. Fidelidade, promoções, cadastro de equipe e relatórios continuam como evolução conceitual.
