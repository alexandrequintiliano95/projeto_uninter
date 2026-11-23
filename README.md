# Projeto Uninter: API Raízes do Nordeste

> Nota: trechos alterados com apoio de IA (Claude Code) e revisados pelo autor.

Back-end da rede fictícia de restaurantes **Raízes do Nordeste**, desenvolvido para o Projeto Multidisciplinar da Uninter (trilha Back-end). A API cuida de pedidos em vários canais com reserva de estoque, pagamento simulado, preparo e entrega, ajustes de estoque, programa de fidelidade e consentimentos da LGPD.

**Repositório:** https://github.com/alexandrequintiliano95/projeto_uninter

**Tecnologias:** Python, FastAPI, SQLAlchemy, Alembic, SQLite, PyJWT, pwdlib (Argon2), pytest e Postman.

## O que a API faz

- Cadastro público de cliente e login com JWT para quatro perfis: cliente, atendente, cozinha e gerente.
- Cardápio por unidade, com preço e saldo próprios de cada unidade.
- Pedido nos canais `APP`, `WEB`, `PICKUP`, `BALCAO` e `TOTEM`, com reserva de estoque por 15 minutos.
- Pagamento simulado (aprovado, recusado ou falha `503`), cancelamento antes do pagamento e expiração automática da reserva.
- Fluxo de preparo e entrega: `CONFIRMADO` → `EM_PREPARO` → `PRONTO` → `ENTREGUE`, cada etapa liberada só para o perfil certo.
- Entrada e saída de estoque pelo gerente, com motivo e histórico.
- Fidelidade: 1 ponto por real pago e resgate de 100 pontos por R$ 5,00 de desconto, com consentimento.
- Consentimentos da LGPD (fidelidade e marketing) com histórico, e auditoria das operações por unidade.
- Um formato único de erro em todas as respostas: `{error, message, details, timestamp, path}`.

## Requisitos

- **Python 3.11 ou superior.** O projeto foi desenvolvido e testado com o Python 3.14.6, no Windows 11.
- Git.
- Opcional, para a coleção de testes: Postman, ou Node.js para rodar o Newman.

## Instalação

**Linux ou macOS (bash):**

```bash
git clone https://github.com/alexandrequintiliano95/projeto_uninter.git
cd projeto_uninter
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/alexandrequintiliano95/projeto_uninter.git
cd projeto_uninter
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

No Git Bash do Windows, ative o ambiente com `source .venv/Scripts/activate`. Os demais comandos deste README são iguais em todos os sistemas e devem ser executados na raiz do projeto, com o ambiente ativado.

## Configuração

A API, o seed e o Alembic leem as mesmas variáveis, do ambiente ou do arquivo `.env` na raiz. O `.env` é opcional e não vai para o git. Sem ele, valem os padrões abaixo, suficientes para rodar localmente.

| Variável | Para que serve | Padrão |
| --- | --- | --- |
| `DATABASE_URL` | Banco de dados | `sqlite:///./raizes.db` (arquivo na raiz do projeto) |
| `JWT_SECRET` | Segredo que assina os tokens | Um segredo fixo de desenvolvimento, que não deve ser usado fora da máquina local |

Para gerar um segredo aleatório:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Banco de dados

```bash
alembic upgrade head
python seed.py
```

- O `alembic upgrade head` cria ou atualiza as tabelas. As migrações são `0001` (modelo inicial), `0002` (histórico de estoque) e `0003` (fidelidade).
- O `python seed.py` cria 2 unidades, 3 produtos, 5 usuários e as ofertas com estoque. Se o banco já tiver dados, ele não faz nada.
- **Para começar do zero:** apague o `raizes.db` (`rm raizes.db` no bash ou `Remove-Item raizes.db` no PowerShell) e rode os dois comandos de novo.
- **Banco criado antes da fidelidade:** rode `alembic upgrade head` de novo para aplicar as migrações que faltam.

## Executar a API

```bash
uvicorn app.main:app --reload
```

A documentação interativa (Swagger) fica em http://127.0.0.1:8000/docs. Para usar as rotas protegidas:

1. Chame `POST /auth/login` com um dos usuários abaixo.
2. Copie o `access_token` da resposta.
3. Clique em **Authorize** e cole o token.

## Usuários do seed

Contas fictícias, apenas para testes locais:

| Perfil | Unidade | E-mail | Senha |
| --- | --- | --- | --- |
| Cliente | Nenhuma | `cliente@raizes.local` | `Cliente@123` |
| Atendente | Recife Centro (1) | `atendente.recife@raizes.local` | `Atendente@123` |
| Cozinha | Recife Centro (1) | `cozinha.recife@raizes.local` | `Cozinha@123` |
| Gerente | Recife Centro (1) | `gerente.recife@raizes.local` | `Gerente@123` |
| Gerente | Caruaru (2) | `gerente.caruaru@raizes.local` | `Gerente@123` |

Novos clientes podem ser criados em `POST /auth/cadastro`.

## Testes

Execute nesta ordem:

1. **Testes automatizados:**

   ```bash
   python -m pytest -q
   ```

   Não precisam da API rodando nem do seed: cada teste usa um banco SQLite temporário próprio, então o `raizes.db` não é alterado.

2. **Coleção Postman:** com o banco migrado e populado e a API rodando (seções acima), importe `postman/raizes-backend.postman_collection.json` no Postman e execute a coleção inteira no Collection Runner, na ordem das pastas. Pela linha de comando, com Node.js instalado:

   ```bash
   npx newman run postman/raizes-backend.postman_collection.json
   ```

   São 54 requisições em 7 pastas, com asserções em todas. A coleção pode ser executada várias vezes sobre o mesmo banco.

Os cenários positivos e negativos, as evidências de execução e os detalhes estão no [plano de testes](docs/PLANO_DE_TESTES.md).

## Endpoints

| Método | Rota | Quem pode usar |
| --- | --- | --- |
| `GET` | `/health` | Público |
| `POST` | `/auth/cadastro` | Público (cria cliente) |
| `POST` | `/auth/login` | Público |
| `GET` | `/unidades` | Público |
| `GET` | `/unidades/{id}/cardapio` | Público |
| `POST` | `/pedidos` | Cliente, atendente e gerente |
| `GET` | `/pedidos`, `/pedidos/{id}` | Autenticado: cliente vê os próprios pedidos; equipe vê os da própria unidade |
| `POST` | `/pedidos/{id}/pagamentos/mock` | Cliente, atendente e gerente |
| `POST` | `/pedidos/{id}/cancelamento` | Cliente, atendente e gerente, antes do pagamento |
| `PATCH` | `/pedidos/{id}/status` | Cozinha e gerente (preparo e pronto); atendente e gerente (entrega) |
| `POST`, `GET` | `/unidades/{id}/estoque/movimentacoes` | Gerente da unidade |
| `GET`, `POST` | `/me/consentimentos` | Cliente |
| `GET` | `/me/fidelidade` | Cliente |
| `GET` | `/auditoria` | Gerente (eventos da própria unidade) |

Requests, respostas e códigos de erro de cada rota estão no [contrato da API](docs/API.md).

## Estrutura do projeto

```text
app/
  domain/            regras de negócio, enums e erros (sem framework)
  application/       casos de uso: pedidos, estoque, fidelidade, cadastro...
  infrastructure/    banco, modelos ORM, repositórios, JWT, senha e configuração
  api/               rotas FastAPI, schemas e formato único de erro
  main.py            cria a aplicação
migrations/          migrações do Alembic
tests/               testes pytest (domínio, API e migrações)
postman/             coleção de testes da API
docs/                modelo, contrato, arquitetura, diagramas, plano de testes e evidências
seed.py              dados iniciais
```

A divisão em camadas está explicada em [docs/ARQUITETURA.md](docs/ARQUITETURA.md).

## Documentação

- [Modelo: permissões, status e DER](docs/MODELO.md)
- [Contrato da API](docs/API.md)
- [Arquitetura em camadas](docs/ARQUITETURA.md)
- [Plano de testes](docs/PLANO_DE_TESTES.md)
- [Casos de uso e caso de uso crítico](docs/CASOS_DE_USO.md)
- [Tratamento de dados pessoais (LGPD)](docs/LGPD.md)
- [Regras de promoção (proposta, não implementada)](docs/PROMOCOES.md)
- [Diagramas da solução: casos de uso, DER, classes e sequência](docs/DIAGRAMAS.md)
- [Plano de execução](PLAN.md) e [registro da revisão do plano](PLAN-REVIEW-LOG.md)
- [Roteiro do relatório acadêmico](docs/RELATORIO_MODELO.md)
- [Relatório acadêmico em PDF](entrega/4250113_Projeto_Back_End.pdf) e [versão editável em DOCX](entrega/4250113_Projeto_Back_End.docx)

## Uso de IA

Partes do código e da documentação foram elaboradas com apoio de IA. Cada arquivo nessa situação traz uma nota no topo, e a declaração completa de uso de IA está no relatório acadêmico.
