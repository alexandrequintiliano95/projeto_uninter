# Diagramas da solução

Os diagramas representam o MVP implementado. O DER completo está em [MODELO.md](MODELO.md).

## Casos de uso

```mermaid
flowchart LR
    Cliente[Cliente]
    Atendente[Atendente]
    Cozinha[Cozinha]
    Gerente[Gerente]
    API((API Raízes do Nordeste))
    Gateway[Pagamento mock]

    Cliente -->|login, cardápio, pedido próprio, pagamento| API
    Atendente -->|pedido balcão, entrega, consulta da unidade| API
    Cozinha -->|consulta e preparo| API
    Gerente -->|consulta, preparo, entrega e ajustes locais| API
    API -->|solicita resultado| Gateway
```

Caso de uso principal: o usuário autenticado cria um pedido para uma unidade, o estoque é reservado, o pagamento mock retorna aprovação ou recusa e a API atualiza o pedido. A cozinha conduz o preparo e o atendente registra a entrega.

## Classes de domínio

```mermaid
classDiagram
    class Unidade
    class Usuario {
      perfil
      unidade_id
    }
    class Produto
    class ProdutoUnidade {
      preco_centavos
      saldo_livre
      saldo_reservado
    }
    class Pedido {
      canal_pedido
      status
      total_centavos
      expira_em
    }
    class ItemPedido {
      quantidade
      preco_unitario_centavos
    }
    class Pagamento {
      status
      valor_centavos
    }
    class Auditoria
    class MovimentacaoEstoque {
      tipo
      quantidade
      motivo
      saldo_livre_anterior
      saldo_livre_novo
    }

    Unidade "1" --> "0..*" Usuario
    Unidade "1" --> "0..*" ProdutoUnidade
    Produto "1" --> "0..*" ProdutoUnidade
    Unidade "1" --> "0..*" Pedido
    Usuario "1" --> "0..*" Pedido : cria
    Pedido "1" --> "1..*" ItemPedido
    ProdutoUnidade "1" --> "0..*" ItemPedido
    Pedido "1" --> "0..1" Pagamento
    Usuario "1" --> "0..*" Auditoria
    ProdutoUnidade "1" --> "0..*" MovimentacaoEstoque
    Usuario "1" --> "0..*" MovimentacaoEstoque : registra
```

## Sequência do fluxo crítico

```mermaid
sequenceDiagram
    actor Cliente
    participant API
    participant Banco
    participant Mock as Pagamento mock
    actor Cozinha
    actor Atendente

    Cliente->>API: POST /auth/login
    API->>Banco: valida usuário e senha
    Banco-->>API: usuário ativo
    API-->>Cliente: JWT
    Cliente->>API: POST /pedidos
    API->>Banco: valida oferta e reserva estoque
    Banco-->>API: pedido aguardando pagamento
    API-->>Cliente: 201 pedido
    Cliente->>API: POST /pedidos/{id}/pagamentos/mock
    API->>Mock: solicita aprovação ou recusa
    Mock-->>API: resultado
    API->>Banco: grava pagamento, status e auditoria
    API-->>Cliente: pedido confirmado ou cancelado
    Cozinha->>API: PATCH status {"status":"EM_PREPARO"}
    API->>Banco: muda de CONFIRMADO para EM_PREPARO
    Cozinha->>API: PATCH status {"status":"PRONTO"}
    API->>Banco: muda de EM_PREPARO para PRONTO
    Atendente->>API: PATCH status {"status":"ENTREGUE"}
    API->>Banco: muda de PRONTO para ENTREGUE
```
