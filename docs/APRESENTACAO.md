# Projeto Raízes do Nordeste
## Visão geral do back-end

Alexandre Quintiliano  
RU 4250113  
Análise e Desenvolvimento de Sistemas  
Polo São José  
Semestre 8º

> Nota: elaborado com apoio de IA (Claude Code) e revisado pelo autor.

---

# 1. O problema do estudo de caso

Uma rede de restaurantes nordestinos com várias unidades precisa de um back-end que:

- receba pedidos por canais diferentes: app, web, retirada, balcão e totem;
- controle cardápio, preço e estoque de cada unidade;
- simule o pagamento e acompanhe o preparo e a entrega;
- tenha perfis de acesso, auditoria e um programa de fidelidade;
- trate os dados pessoais conforme a LGPD.

---

# 2. A solução

Uma API REST com:

- Python e FastAPI;
- SQLAlchemy, Alembic e SQLite;
- JWT para login e Argon2 para senha;
- pytest e Postman para os testes.

O código está dividido em quatro camadas: domínio (regras), aplicação (casos de uso), infraestrutura (banco e segurança) e API (rotas). As regras de negócio não dependem do framework.

---

# 3. Como o pedido funciona

1. O cliente consulta o cardápio da unidade.
2. Cria o pedido: o estoque fica reservado por 15 minutos.
3. O pagamento simulado é aprovado, recusado ou falha (`503`).
4. Aprovado, a cozinha prepara e o atendente entrega.

Status: `AGUARDANDO_PAGAMENTO` → `CONFIRMADO` → `EM_PREPARO` → `PRONTO` → `ENTREGUE`.

Antes do pagamento, o pedido pode ir para `CANCELADO`, por recusa, por cancelamento do cliente ou por prazo vencido. Nesses casos, a reserva volta ao estoque.

---

# 4. Perfis e permissões

| Perfil | O que faz |
| --- | --- |
| Cliente | Cria conta, faz e paga os próprios pedidos, cancela antes do pagamento, gerencia consentimentos e pontos. |
| Atendente | Registra pedidos de balcão e totem e entrega pedidos prontos, só na própria unidade. |
| Cozinha | Vê só os pedidos pagos da própria unidade e avança o preparo. |
| Gerente | Faz tudo o que o atendente e a cozinha fazem, movimenta o estoque e consulta a auditoria da unidade. |

As permissões são conferidas no servidor. Pedido de outra pessoa ou de outra unidade responde como inexistente (`404`).

---

# 5. Além do fluxo principal

- **Cadastro de cliente** com aceite dos termos e senha forte.
- **Cancelamento** antes do pagamento, com devolução da reserva.
- **Falha simulada** do provedor de pagamento: `503`, sem perder o pedido.
- **Entrada e saída de estoque** pelo gerente, com motivo e histórico.
- **Fidelidade:** 1 ponto por real pago; 100 pontos valem R$ 5,00 de desconto, até 50% do pedido.
- **Promoções:** regras documentadas como proposta, sem implementação.

---

# 6. Modelo do banco

São 11 tabelas, criadas por 3 migrações do Alembic:

- unidades, usuários, produtos e ofertas por unidade (preço e estoque);
- pedidos, itens e pagamentos;
- consentimentos, auditoria, movimentações de estoque e extrato de fidelidade.

Valores em centavos, preço copiado no item na hora da compra e restrições no banco que impedem saldo negativo. O DER está em `docs/img/der.png`.

---

# 7. Endpoints principais

- `POST /auth/cadastro` e `POST /auth/login`
- `GET /unidades` e `GET /unidades/{id}/cardapio`
- `POST /pedidos`, `GET /pedidos` (filtros `canalPedido` e `status`) e `GET /pedidos/{id}`
- `POST /pedidos/{id}/pagamentos/mock` e `POST /pedidos/{id}/cancelamento`
- `PATCH /pedidos/{id}/status`
- `POST` e `GET /unidades/{id}/estoque/movimentacoes`
- `GET` e `POST /me/consentimentos` e `GET /me/fidelidade`
- `GET /auditoria`

Todo erro sai no mesmo formato: `error`, `message`, `details`, `timestamp` e `path`. A documentação interativa fica em `/docs`.

---

# 8. Segurança e LGPD

- Senha guardada só como hash Argon2; token JWT expira em 60 minutos.
- Cadastro com dados mínimos: nome, e-mail e senha. Sem CPF, endereço ou cartão.
- Consentimentos de fidelidade e marketing separados, opcionais e com histórico.
- Auditoria das operações sem e-mail, senha ou token.
- Base legal e retenção de cada dado, direitos do titular e anonimização proposta em `docs/LGPD.md`.

---

# 9. Testes e evidências

- **Testes automatizados (pytest):** regras de domínio, API e migrações, cada teste com banco temporário próprio.
- **Coleção Postman:** 54 requisições em 7 pastas, com asserções em todas. Executada com o Newman: 131 asserções, nenhuma falha.
- **Plano de testes:** 12 cenários positivos e 17 negativos, cada um ligado à requisição e ao teste que o comprovam.
- **Reprodução:** o README foi seguido do zero numa cópia limpa do projeto, com instalação, migração, seed e testes.

---

# 10. Uso de IA

Parte do código e da documentação foi elaborada com apoio de IA (Claude Code). Cada arquivo nessa situação tem uma nota no topo. O conteúdo foi revisado pelo autor, e as decisões de projeto foram tomadas ou aprovadas por ele. A declaração completa está no relatório.

---

# 11. O que ainda falta

- Gerar o PDF acadêmico em ABNT, com as evidências e imagens.
- Revisar os textos com as próprias palavras.
- Conferir no AVA as normas, o nome do arquivo e o prazo.
- Conferir o acesso público ao repositório.
- Preencher o nome do professor.

---

# Encerramento

O back-end cobre o fluxo completo do pedido, com estoque, pagamento simulado, fidelidade e LGPD, e está testado e documentado. Falta transformar essa base em relatório acadêmico.
