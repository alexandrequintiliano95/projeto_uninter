# Projeto Raízes do Nordeste
## Visão geral do back-end

Alexandre Quintiliano  
RU 4250113  
Análise e Desenvolvimento de Sistemas  
Polo São José  
Semestre 8º

---

# 1. O problema do estudo de caso

O sistema precisa atender pedidos de uma rede de alimentação regional.

O back-end foi pensado para controlar:

- unidades de atendimento;
- cardápio e estoque;
- pedidos feitos por canais diferentes;
- pagamento simulado;
- preparo e entrega;
- usuários, permissões e auditoria.

---

# 2. O que foi escolhido

Foi criado um MVP de API REST usando:

- Python;
- FastAPI;
- SQLAlchemy;
- SQLite;
- Alembic;
- JWT para sessão;
- Argon2 para senha.

O objetivo foi manter a primeira versão simples, executável e fácil de demonstrar.

---

# 3. Como o pedido funciona

1. O cliente acessa uma unidade.
2. O cardápio é consultado.
3. O pedido é criado com os itens disponíveis.
4. O estoque é reservado.
5. O pagamento simulado é aprovado ou recusado.
6. O pedido segue para preparo, entrega ou cancelamento.
7. Cada alteração importante fica registrada na auditoria.

---

# 4. Perfis e permissões

## Cliente

Consulta unidades, consulta cardápio e cria os próprios pedidos.

## Atendente

Consulta pedidos e altera pedidos da unidade permitida.

## Cozinha

Consulta pedidos e atualiza as etapas de preparo.

## Gerente

Consulta pedidos, auditoria e dados das unidades sob sua responsabilidade.

As permissões são verificadas no servidor, não apenas na interface.

---

# 5. Modelo do banco

O banco foi organizado em tabelas para:

- usuários;
- unidades;
- produtos;
- produtos por unidade;
- pedidos;
- itens do pedido;
- pagamentos;
- consentimentos;
- auditoria.

A primeira migração é executada com Alembic. O arquivo SQLite é criado localmente e não é enviado ao Git.

---

# 6. Endpoints principais

- `POST /auth/login`: autenticação.
- `GET /unidades`: lista unidades disponíveis.
- `GET /unidades/{id}/cardapio`: consulta o cardápio.
- `POST /pedidos`: cria pedido.
- `GET /pedidos/{id}`: consulta um pedido.
- `GET /pedidos`: lista pedidos com filtros.
- `POST /pedidos/{id}/pagamentos/mock`: simula pagamento.
- `PATCH /pedidos/{id}/status`: altera o status.
- `GET /auditoria`: consulta o histórico permitido.

O FastAPI também gera a documentação interativa em `/docs`.

---

# 7. Status e regras do pedido

Os status usados são:

`CRIADO` → `AGUARDANDO_PAGAMENTO` → `PAGO` → `EM_PREPARO` → `PRONTO` → `EM_ENTREGA` → `ENTREGUE`

Também existem os caminhos de `CANCELADO` e `EXPIRADO`.

Regras implementadas:

- pedido sem pagamento expira em 15 minutos;
- pagamento recusado cancela o pedido;
- estoque insuficiente impede a criação;
- pedido entregue não pode voltar para uma etapa anterior.

---

# 8. Segurança e LGPD

- senha armazenada com hash Argon2;
- autenticação por token JWT;
- rotas protegidas por perfil;
- usuário limitado à própria unidade quando aplicável;
- registro de consentimento;
- trilha de auditoria para ações relevantes;
- dados de teste fictícios.

O pagamento é apenas simulado. Não foram armazenados dados reais de cartão.

---

# 9. Testes e demonstração

Foram criados testes automatizados para:

- login;
- acesso sem token;
- criação de pedido;
- bloqueio de canal inválido;
- pagamento aprovado;
- pagamento recusado;
- filtro de pedidos.

Resultado atual: `7 passed`.

Também foi criada uma coleção Postman com 11 requisições para demonstrar o fluxo.

---

# 10. O que já está pronto

- estrutura do projeto;
- banco e migração inicial;
- dados fictícios para teste;
- autenticação;
- regras de permissão;
- fluxo de pedidos;
- pagamento simulado;
- auditoria;
- testes automatizados;
- documentação da API;
- modelo de relatório acadêmico.

---

# 11. O que ainda precisa ser feito

- executar os testes no ambiente final;
- revisar os textos com as próprias palavras;
- inserir as evidências e imagens exigidas pelo roteiro;
- ajustar a formatação acadêmica;
- exportar o relatório para PDF;
- conferir os critérios específicos da instituição antes da entrega.

O professor foi deixado em branco porque o nome ainda não foi localizado.

---

# Encerramento

O projeto já possui uma base funcional para demonstrar o back-end.

O próximo trabalho é transformar essa base técnica em documentação acadêmica própria, com evidências da execução e revisão final do roteiro.

