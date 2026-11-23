# Diagramas da solução

> Nota: trechos alterados com apoio de IA (Claude Code) e revisados pelo autor.

Os diagramas representam o MVP implementado. O DER, com restrições e regras de cada tabela, está detalhado em [MODELO.md](MODELO.md).

## Casos de uso

![Diagrama UML de casos de uso](img/casos-de-uso.png)

Atores, lista completa dos casos de uso e a descrição detalhada do caso crítico (Realizar pedido) estão em [CASOS_DE_USO.md](CASOS_DE_USO.md).

## DER

![DER da API Raízes do Nordeste](img/der.png)

Versão vetorial em [img/der.svg](img/der.svg). A imagem é gerada a partir do DER em Mermaid do [MODELO.md](MODELO.md), com o código em [img/der.mmd](img/der.mmd).

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
      desconto_centavos
      pontos_resgatados
      expira_em
    }
    class FidelidadeMovimento {
      tipo
      pontos
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
    Usuario "1" --> "0..*" FidelidadeMovimento : acumula
    Pedido "1" --> "0..*" FidelidadeMovimento
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
