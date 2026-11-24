# Modelo do Back-end

> Nota: trechos alterados com apoio de IA (Claude Code) e revisados pelo autor.

Decisões do fluxo pedido → pagamento simulado → preparo → entrega: permissões, estados, reserva de estoque e DER. Tudo o que está descrito aqui está implementado na API, exceto o que o texto indica como proposta, evolução ou limitação. A seção 5 aponta o teste que comprova cada regra.

## 1. Recorte do MVP

- Uma API FastAPI e um banco SQLite, com duas unidades e dados fictícios no seed.
- Quatro perfis fixos. Cada funcionário pertence a uma unidade; o cliente não pertence a uma unidade.
- Estoque contado em unidades inteiras de produto pronto. Ingredientes e receitas ficam como evolução.
- Preço, disponibilidade e estoque local ficam juntos em `produto_unidade`.
- Pagamento totalmente simulado, à vista e pelo valor integral. Um pedido tem no máximo um resultado de pagamento.
- Compra não exige adesão à fidelidade ou marketing. Com consentimento `FIDELIDADE` ativo, o cliente ganha 1 ponto por real pago e pode usar cada 100 pontos como R$ 5,00 de desconto, até 50% do pedido. Promoções por unidade estão documentadas como proposta em [PROMOCOES.md](PROMOCOES.md), sem implementação. Validade de pontos, níveis de cliente, campanhas da matriz e relatórios ficam descritos como evolução.

## 2. Perfis e permissões

| Ação | CLIENTE | ATENDENTE | COZINHA | GERENTE |
| --- | --- | --- | --- | --- |
| Consultar unidades e cardápio | Permitido, inclusive sem login | Permitido | Permitido | Permitido |
| Criar conta | Cadastro público, sem login; a conta nasce como CLIENTE | Não (equipe vem do seed) | Não | Não |
| Criar pedido | Para si, em unidade ativa | Na própria unidade | Não | Na própria unidade |
| Consultar/listar pedidos e filtrar canal/status | Somente próprios | Da própria unidade | Da própria unidade, apenas confirmados, em preparo, prontos ou entregues | Da própria unidade |
| Solicitar pagamento mock | Do próprio pedido | De pedido da própria unidade | Não | De pedido da própria unidade |
| Cancelar antes do pagamento | Próprio pedido | Pedido da própria unidade | Não | Pedido da própria unidade |
| Iniciar preparo e marcar pronto | Não | Não | Na própria unidade | Na própria unidade |
| Marcar entregue | Não | Na própria unidade | Não | Na própria unidade |
| Registrar entrada e saída de estoque local | Não | Não | Não | Na própria unidade, com motivo registrado |
| Ajustar oferta e preço | Não | Não | Não | Evolução: hoje oferta e preço vêm do seed |
| Consultar auditoria | Não | Não | Não | Da própria unidade |
| Consultar/alterar consentimentos | Somente próprios | Não altera (a consulta devolve lista vazia) | Não altera | Não altera |
| Consultar saldo e extrato de pontos; resgatar pontos no pedido | Somente próprios, com consentimento `FIDELIDADE` ativo para resgatar | Não | Não | Não |

Regras de aplicação:

1. O servidor obtém usuário, perfil e unidade do usuário autenticado. IDs e perfis enviados no corpo não concedem acesso. Tokens precisam estar válidos e o usuário ativo.
2. O cliente cria pedidos com `cliente_id = criado_por_id = usuário autenticado`. Não escolhe outro cliente no request.
3. Atendente e gerente criam pedidos presenciais com `criado_por_id = usuário autenticado` e `cliente_id = NULL`. Não é necessário cadastrar o consumidor do balcão. Vinculação posterior e fidelidade nesses pedidos ficam fora do MVP.
4. Canais permitidos: cliente usa `APP`, `WEB` ou `PICKUP`; atendente/gerente usam `BALCAO`, `TOTEM` ou `PICKUP`. O totem é representado por chamadas autenticadas de um atendente no protótipo. O canal não altera permissões.
5. Gerente não possui acesso global. Cadastros de unidades, produtos e equipe entram pelo seed; administração da matriz e cadastro de equipe pela API ficam como evolução. O cadastro público (`POST /auth/cadastro`) cria apenas clientes: perfil e unidade nunca vêm do request, o aceite dos termos de uso é obrigatório e os consentimentos de fidelidade e marketing são opcionais e separados.
6. Respostas de cozinha trazem ID do pedido, canal, itens e status, sem nome, e-mail, senha ou token de clientes. Os demais perfis também recebem apenas os campos necessários.
7. Sem autenticação: `401`. Perfil sem permissão: `403`. Registro inexistente ou fora da unidade/propriedade permitida: `404`. Listagens já aplicam o filtro de acesso e possuem paginação.

## 3. Fluxo de status do pedido

```mermaid
stateDiagram-v2
    [*] --> AGUARDANDO_PAGAMENTO: criar e reservar estoque
    AGUARDANDO_PAGAMENTO --> CONFIRMADO: pagamento mock aprovado
    AGUARDANDO_PAGAMENTO --> CANCELADO: recusa, cancelamento ou prazo vencido
    CONFIRMADO --> EM_PREPARO: cozinha ou gerente
    EM_PREPARO --> PRONTO: cozinha ou gerente
    PRONTO --> ENTREGUE: atendente ou gerente
    ENTREGUE --> [*]
    CANCELADO --> [*]
```

| Origem | Destino | Quem provoca | Efeito no estoque |
| --- | --- | --- | --- |
| Sem pedido | AGUARDANDO_PAGAMENTO | Cliente, atendente ou gerente autorizado | Reserva os itens |
| AGUARDANDO_PAGAMENTO | CONFIRMADO | Serviço de pagamento mock, após aprovação | Consome a reserva |
| AGUARDANDO_PAGAMENTO | CANCELADO | Serviço mock após recusa; cliente/atendente/gerente autorizado; ou expiração | Devolve a reserva |
| CONFIRMADO | EM_PREPARO | Cozinha ou gerente da unidade | Nenhum |
| EM_PREPARO | PRONTO | Cozinha ou gerente da unidade | Nenhum |
| PRONTO | ENTREGUE | Atendente ou gerente da unidade | Nenhum |

- A rota de status só permite as transições manuais da tabela. O cliente não pode definir `CONFIRMADO` diretamente; isso depende do pagamento aprovado.
- Cancelamento voluntário só ocorre em `AGUARDANDO_PAGAMENTO`. Cancelamento de pedido pago e estorno ficam fora deste MVP; tentativa retorna `409`.
- `CANCELADO` e `ENTREGUE` são finais. Não se pulam etapas nem se reabre pedido. Repetir o status atual, após conferir a permissão, devolve o estado existente sem repetir efeitos ou auditoria de alteração.
- `motivo_cancelamento` recebe `SOLICITADO`, `PAGAMENTO_RECUSADO` ou `PRAZO_EXPIRADO`. É obrigatório quando o pedido é cancelado e nulo nos demais estados.
- Pagamento tem seus próprios resultados `APROVADO` e `RECUSADO`. Cancelamento manual e expiração ocorrem sem registro de pagamento. O cancelamento usa a rota própria `POST /pedidos/{id}/cancelamento`, e não a rota de status.

### Reserva e prazo

Para o protótipo, fica adotado o prazo de **15 minutos** a partir da criação. Esse tempo é uma decisão do projeto, não uma exigência dos PDFs. O servidor grava `expira_em` em UTC; a reserva vence quando o relógio do servidor alcança esse instante, somente se o pedido ainda aguarda pagamento.

A liberação é feita por uma única função da camada de aplicação (`expirar_pedidos`), chamada antes de criar, consultar, listar, pagar ou cancelar pedidos, de mostrar o cardápio e de movimentar o estoque da unidade. Ela cancela os pedidos vencidos com motivo `PRAZO_EXPIRADO`, devolve as reservas, estorna pontos resgatados e grava `PEDIDO_EXPIRADO` na auditoria. Assim, não é necessário um processo agendado. Se a API estiver parada, a atualização acontece na próxima operação, e um pagamento após o vencimento é recusado com `409`.

| Operação, para quantidade Q | saldo_livre | saldo_reservado |
| --- | --- | --- |
| Criar pedido | diminui Q | aumenta Q |
| Aprovar pagamento | não muda | diminui Q |
| Recusar/cancelar/expirar | aumenta Q | diminui Q |

O saldo físico antes do consumo é `saldo_livre + saldo_reservado`. Ajustes do gerente alteram apenas o saldo livre e nunca retiram itens reservados. Nenhum saldo pode ser negativo. Preço ou disponibilidade alterados depois da compra não modificam o pedido já reservado.

### Transações e repetição

Criação, pagamento, cancelamento e expiração são operações de banco atômicas: pedido, itens, estoque, pagamento, pontos e auditoria envolvidos são confirmados juntos no fim da operação ou desfeitos juntos. A reserva exige saldo suficiente para todos os itens, e as restrições `CHECK` do banco impedem saldo negativo.

**Limitação conhecida:** a reserva lê o saldo e depois grava o novo valor, sem bloquear a linha. Duas requisições realmente simultâneas disputando o último item não foram testadas. Para produção, a proposta é uma atualização condicional (`UPDATE ... SET saldo_livre = saldo_livre - Q WHERE saldo_livre >= Q`, conferindo quantas linhas foram alteradas) ou o bloqueio da linha (`SELECT ... FOR UPDATE`) num banco servidor.

O simulador recebe um cenário (`APROVADO`, `RECUSADO` ou `FALHA`) e retorna um resultado local, sem chamada a provedor real. Há uma restrição `UNIQUE(pedido_id)` em `pagamento`. Repetir a mesma simulação retorna o pagamento já registrado; tentar trocar o resultado retorna `409`. A permissão é conferida mesmo na repetição. Não há segunda tentativa em pedido recusado; cria-se um novo pedido. O cenário `FALHA` simula o provedor fora do ar: retorna `503`, mantém o pedido aguardando, não grava pagamento e registra `PAGAMENTO_FALHA` na auditoria; a reserva continua sujeita ao prazo e o pedido pode ser pago depois.

## 4. DER

![DER da API Raízes do Nordeste](img/der.png)

Versão vetorial em [img/der.svg](img/der.svg). O diagrama em Mermaid abaixo é a fonte da imagem.

São onze tabelas: as nove da migração inicial, `movimentacao_estoque` (migração `0002`) e `fidelidade_movimento` (migração `0003`, que também acrescenta `desconto_centavos` e `pontos_resgatados` ao pedido). Os nomes abaixo são os nomes internos do banco, usados também nas respostas da API. O corpo de `POST /pedidos` e os filtros da listagem usam os nomes do roteiro (`unidadeId`, `canalPedido`, `produtoId`, `pontosResgatados`; filtros `canalPedido` e `status`), e o corpo aceita também os nomes internos. Campos terminados em `_centavos` são inteiros: por exemplo, R$ 12,50 é gravado como `1250`, evitando arredondamento de ponto flutuante.

```mermaid
erDiagram
    UNIDADE o|--o{ USUARIO : vincula_equipe
    UNIDADE ||--o{ PRODUTO_UNIDADE : oferece
    PRODUTO ||--o{ PRODUTO_UNIDADE : possui_oferta
    UNIDADE ||--o{ PEDIDO : recebe
    USUARIO ||--o{ PEDIDO : cria
    USUARIO o|--o{ PEDIDO : cliente_opcional
    PEDIDO ||--|{ ITEM_PEDIDO : contem
    PRODUTO_UNIDADE ||--o{ ITEM_PEDIDO : origina
    PEDIDO ||--o| PAGAMENTO : recebe_resultado
    USUARIO ||--o{ CONSENTIMENTO_EVENTO : registra
    USUARIO o|--o{ AUDITORIA : executa
    UNIDADE o|--o{ AUDITORIA : contextualiza
    PRODUTO_UNIDADE ||--o{ MOVIMENTACAO_ESTOQUE : movimenta
    USUARIO ||--o{ MOVIMENTACAO_ESTOQUE : registra
    USUARIO ||--o{ FIDELIDADE_MOVIMENTO : acumula
    PEDIDO ||--o{ FIDELIDADE_MOVIMENTO : origina

    UNIDADE {
        int id PK
        string nome
        string cidade
        string uf
        boolean ativa
    }
    USUARIO {
        int id PK
        int unidade_id FK "nulo para CLIENTE"
        string nome
        string email UK
        string senha_hash
        string perfil
        boolean ativo
    }
    PRODUTO {
        int id PK
        string nome
        string descricao
        boolean ativo
    }
    PRODUTO_UNIDADE {
        int id PK
        int unidade_id FK
        int produto_id FK
        int preco_centavos
        int saldo_livre
        int saldo_reservado
        boolean ativo
    }
    PEDIDO {
        int id PK
        int unidade_id FK
        int criado_por_id FK
        int cliente_id FK "opcional"
        string canal_pedido
        string status
        int total_centavos "valor a pagar, já com desconto"
        int desconto_centavos
        int pontos_resgatados
        string motivo_cancelamento "opcional"
        datetime criado_em
        datetime atualizado_em
        datetime expira_em
    }
    ITEM_PEDIDO {
        int id PK
        int pedido_id FK
        int produto_unidade_id FK
        string nome_produto
        int quantidade
        int preco_unitario_centavos
    }
    PAGAMENTO {
        int id PK
        int pedido_id FK, UK
        string status
        int valor_centavos
        datetime criado_em
    }
    CONSENTIMENTO_EVENTO {
        int id PK
        int usuario_id FK
        string finalidade
        boolean concedido
        string versao_termo
        datetime criado_em
    }
    AUDITORIA {
        int id PK
        int usuario_id FK "nulo quando acao automatica"
        int unidade_id FK "opcional"
        string acao
        string tipo_entidade
        int entidade_id
        string detalhes
        datetime criado_em
    }
    FIDELIDADE_MOVIMENTO {
        int id PK
        int usuario_id FK "cliente"
        int pedido_id FK
        string tipo "CREDITO, DEBITO ou ESTORNO"
        int pontos
        datetime criado_em
    }
    MOVIMENTACAO_ESTOQUE {
        int id PK
        int produto_unidade_id FK
        int usuario_id FK "gerente que registrou"
        string tipo "ENTRADA ou SAIDA"
        int quantidade
        string motivo
        int saldo_livre_anterior
        int saldo_livre_novo
        datetime criado_em
    }
```

Na relação da equipe, cada funcionário possui exatamente uma unidade; um cliente possui zero. Um pedido sempre tem um criador e pode não ter cliente identificado. A relação `contem` representa a regra de pelo menos um item, validada pela aplicação na transação de criação.

### Restrições de banco e regras da aplicação

| Local | Regra |
| --- | --- |
| Todas as tabelas | PK inteira; FK obrigatória salvo os campos declarados opcionais; datas UTC; impedir exclusão de registros referenciados. Desativar cadastros em vez de apagar histórico. |
| usuario | E-mail normalizado em minúsculas, sem espaços nas extremidades e único; perfil entre os quatro definidos; unidade nula para CLIENTE e obrigatória para funcionários. Não permitir mudança de unidade de funcionário com histórico no MVP. |
| produto_unidade | `UNIQUE(unidade_id, produto_id)`; preço maior que zero; saldos inteiros não negativos. |
| pedido | Canal e status limitados aos valores definidos; total positivo; expiração posterior à criação; motivo compatível com cancelamento. Unidade/criador/cliente/canal não mudam após criar. |
| item_pedido | `UNIQUE(pedido_id, produto_unidade_id)`; quantidade inteira positiva; preço positivo. A aplicação rejeita itens repetidos no request com `422` e exige que todas as ofertas pertençam à unidade do pedido. |
| Valores | O servidor busca o preço da oferta e grava uma cópia no item. Total é a soma de quantidade × preço dos itens; o nome também fica preservado. Valores de preço/total enviados pelo cliente não são usados como autoridade. Não há taxa. O único desconto é o resgate de pontos: `total_centavos` = soma dos itens − `desconto_centavos`, e o pagamento usa esse total. |
| pagamento | Pedido único; valor igual ao total do pedido; resultado entre APROVADO/RECUSADO. Resultado e valor são imutáveis. A aplicação mantém correspondência entre resultado e estado do pedido. |
| consentimento_evento | Finalidade FIDELIDADE ou MARKETING; versão do termo e data obrigatórias. Sem evento, não há consentimento. A opção atual é o evento mais recente por finalidade, ordenado por data e ID. Concessão e revogação acrescentam eventos; não sobrescrevem o histórico. |
| fidelidade_movimento | Tipo `CREDITO`, `DEBITO` ou `ESTORNO`; pontos inteiros positivos; sempre ligado a um pedido. Saldo = créditos + estornos − débitos, nunca negativo (o resgate confere o saldo). Crédito só com consentimento ativo no pagamento; estorno só para pedido com pontos resgatados que foi cancelado. Registros não são editados nem apagados. |
| movimentacao_estoque | Tipo `ENTRADA` ou `SAIDA`; quantidade inteira positiva; motivo obrigatório (3 a 200 caracteres); saldos anterior e novo não negativos. Altera só o saldo livre da oferta: a saída nunca passa do saldo livre e nunca retira itens reservados. Registros não são editados nem apagados. |
| auditoria | Registra criação de pedido, pagamento (inclusive a falha simulada), mudanças de status, cancelamento, expiração, movimentação de estoque, cadastro de cliente e alterações de consentimento. Registra também o acesso a dados pessoais: a consulta individual de um pedido de cliente por funcionário (`DADOS_CLIENTE_CONSULTADOS`) e a consulta da própria auditoria (`AUDITORIA_CONSULTADA`). Guarda os valores anteriores e novos necessários, sem senha, token, e-mail ou conteúdo completo de requests. |

`tipo_entidade` e `entidade_id` identificam o objeto na auditoria, mas não formam uma FK polimórfica: a aplicação valida o alvo ao gravar. Auditoria não tem edição/exclusão por API. Eventos de expiração usam usuário nulo e a unidade do pedido; eventos de consentimento usam a pessoa autenticada e unidade nula. Gerentes não consultam eventos pessoais sem unidade. Cadastro/equipe e permissão são conferidos novamente nas operações; possuir um ID válido não basta.

## 5. Casos comprovados

Cada caso abaixo é verificado por testes automatizados (`python -m pytest`). O [plano de testes](PLANO_DE_TESTES.md) traz também os cenários da coleção Postman.

| # | Caso | Testes |
| --- | --- | --- |
| 1 | Cliente não consulta nem paga pedido de outra pessoa; funcionário não opera outra unidade; IDs e perfis enviados no corpo não concedem acesso. | `test_client_cannot_see_or_pay_another_clients_order`, `test_staff_cancels_only_orders_of_own_unit`, `test_only_manager_of_the_unit_moves_stock`, `test_signup_ignores_profile_and_unit_sent_in_body`, `test_acesso_ao_pedido` |
| 2 | Cozinha não paga nem cancela pedido; atendente não inicia preparo; gerente atua só na própria unidade. | `test_kitchen_cannot_pay_order`, `test_kitchen_cannot_cancel_order`, `test_mudanca_de_status`, `test_only_manager_of_the_unit_moves_stock` |
| 3 | Pedido com canal inválido retorna `422`; canal válido não permitido ao perfil retorna `403`. | `test_invalid_channel_and_invalid_quantity`, `test_client_cannot_create_balcao_order` |
| 4 | Produto sem oferta na unidade, produto desativado, quantidade inválida e falta de estoque são rejeitados sem gravação parcial. | `test_product_without_offer_in_the_unit_is_unavailable`, `test_inactive_product_is_unavailable`, `test_invalid_channel_and_invalid_quantity`, `test_order_beyond_stock_is_rejected_without_reserving` |
| 5 | Duas criações simultâneas disputando a última unidade. | **Não comprovado.** Ver a limitação conhecida na seção 3. |
| 6 | Aprovação, recusa, cancelamento e expiração movimentam a reserva uma única vez, inclusive com repetição. | `test_create_order_and_reject_payment`, `test_client_cancels_own_pending_order`, `test_repeating_cancel_is_idempotent`, `test_payment_result_cannot_be_changed`, `test_expired_order_cannot_be_paid` |
| 7 | Pedido vencido não pode ser pago; a próxima consulta ou operação libera a reserva e registra motivo e auditoria. | `test_expired_order_cannot_be_paid`, `test_menu_releases_expired_reservations` |
| 8 | Não se pula etapa nem se altera pedido finalizado; pedidos pagos não são cancelados. | `test_skipping_a_step_is_conflict`, `test_status_route_cannot_confirm_or_cancel`, `test_mudanca_de_status`, `test_paid_order_cannot_be_cancelled` |
| 9 | Alterar preço ou nome no catálogo não muda os valores nem a identificação do item já comprado. | `test_catalog_change_does_not_alter_existing_order` |
| 10 | Cliente compra sem consentimento; cada finalidade é independente e o histórico é mantido. | `test_purchase_without_consent_earns_no_points`, `test_signup_records_only_the_consents_given`, `test_revoked_consent_freezes_points`, `test_client_consent_and_manager_audit` |
| 11 | A cozinha só enxerga pedidos pagos da própria unidade. | `test_kitchen_only_sees_paid_orders`, `test_cozinha_so_ve_pedidos_pagos_da_propria_unidade` |
