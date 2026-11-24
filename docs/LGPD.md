# Tratamento de dados pessoais (LGPD)

> Nota: elaborado com apoio de IA (Claude Code) e revisado pelo autor.

Este documento descreve como a API Raízes do Nordeste trata dados pessoais à luz da Lei Geral de Proteção de Dados (Lei nº 13.709/2018). Ele separa o que **já está implementado** do que é **proposta para a versão de produção**. Os prazos de retenção são propostas do projeto acadêmico e, numa empresa real, precisariam ser validados pelo jurídico e pelo encarregado de dados.

## Papéis

- **Controlador:** a rede Raízes do Nordeste (empresa fictícia), que decide como e por que os dados são tratados.
- **Titulares:** clientes cadastrados e funcionários (atendentes, cozinha e gerentes).
- **Operador:** o provedor de pagamento, numa versão real (art. 5º, VII). Neste protótipo o pagamento é simulado pela própria API, e nenhum dado vai para terceiros.
- **Encarregado (art. 41):** a ser nomeado pela rede, com o contato divulgado aos titulares.

## Dados tratados

O projeto segue o princípio da **necessidade** (art. 6º, III): o cadastro pede só nome, e-mail e senha. Não há CPF, telefone, endereço nem dados de cartão, porque o pagamento é simulado e o pedido é retirado ou entregue na unidade.

| Dado | Titular | Onde fica | Finalidade | Base legal (art. 7º) | Retenção proposta |
| --- | --- | --- | --- | --- | --- |
| Nome e e-mail | Cliente e funcionário | `usuario` | Criar e manter a conta, identificar quem fez o pedido, fazer login | V: execução de contrato (termos de uso, para o cliente; contrato de trabalho, para o funcionário) | Enquanto a conta estiver ativa. Ao encerrar, anonimizar (ver abaixo). |
| Senha | Cliente e funcionário | `usuario`, só como hash Argon2 | Autenticar | V: execução de contrato | Enquanto a conta estiver ativa. Na anonimização, substituída por um valor aleatório. |
| Perfil e unidade | Funcionário | `usuario` | Controlar o que cada pessoa pode fazer e em qual unidade | V: execução de contrato (de trabalho) | Enquanto durar o vínculo. |
| Pedidos e itens (canal, valores, datas, status) | Cliente | `pedido`, `item_pedido` | Vender, preparar, entregar e prestar contas | V: execução de contrato; II: obrigação legal (fiscal) | 5 anos após o pedido, prazo usado para documentos fiscais (Código Tributário Nacional, arts. 173 e 174). Depois disso, desvincular do cliente. |
| Resultado e valor do pagamento | Cliente | `pagamento` | Confirmar o pedido e prestar contas | V e II | 5 anos, como os pedidos. |
| Eventos de consentimento (finalidade, concedido ou revogado, versão do termo, data) | Cliente | `consentimento_evento` | Provar que o consentimento foi dado ou revogado | II: o controlador precisa provar o consentimento (art. 8º, § 2º) | Enquanto houver tratamento baseado no consentimento e por mais 5 anos após a revogação ou o encerramento da conta, prazo de reclamações de consumo (Código de Defesa do Consumidor, art. 27). |
| Extrato e saldo de pontos | Cliente | `fidelidade_movimento` | Programa de fidelidade | I: consentimento da finalidade `FIDELIDADE` | Enquanto o consentimento estiver ativo. Revogado, o saldo fica congelado por até 12 meses para eventual reativação e depois é eliminado. A eliminação pode ser pedida antes, a qualquer momento. |
| Registros de auditoria (ID do usuário, ação, entidade, data) | Cliente e funcionário | `auditoria` | Segurança, rastreabilidade e prevenção de fraude | IX: legítimo interesse; registro das operações (art. 37) | 5 anos para eventos ligados a pedidos, pagamentos e estoque. A auditoria não guarda e-mail, senha nem token. |
| Movimentações de estoque (ID do gerente, motivo, saldos) | Funcionário | `movimentacao_estoque` | Controle de estoque e responsabilização | V (contrato de trabalho) e IX | 5 anos, como os demais registros operacionais. |
| Token de acesso (ID e perfil) | Cliente e funcionário | Não é guardado no servidor | Autenticar cada requisição | V: execução de contrato | Expira em 60 minutos. |

## Consentimento

Implementado:

- **Separado por finalidade:** fidelidade (`FIDELIDADE`) e marketing (`MARKETING`), cada uma concedida ou revogada de forma independente.
- **Opcional:** a compra não depende de consentimento. No cadastro, as duas opções vêm desmarcadas (`false`) e só geram registro quando a pessoa marca.
- **Comprovável:** cada concessão ou revogação vira um evento novo, com a versão do termo e a data. O histórico nunca é sobrescrito, o que atende ao ônus da prova do art. 8º, § 2º.
- **Revogável a qualquer momento** (art. 8º, § 5º): `POST /me/consentimentos` com `concedido: false`. Revogada a fidelidade, o cliente deixa de acumular e de resgatar pontos.
- **Aceite dos termos não é consentimento:** o aceite dos termos de uso no cadastro tem base na execução do contrato (art. 7º, V). Ele fica registrado na auditoria com a versão aceita, sem o e-mail.

## Direitos do titular (art. 18)

| Direito | Como a API atende hoje | Evolução proposta |
| --- | --- | --- |
| Confirmação e acesso (I e II) | O cliente consulta os próprios pedidos (`GET /pedidos`), consentimentos (`GET /me/consentimentos`) e pontos (`GET /me/fidelidade`). | `GET /me/dados`, reunindo cadastro, pedidos, consentimentos e pontos. |
| Correção (III) | Não há rota. | `PATCH /me` para corrigir nome e e-mail. |
| Anonimização, bloqueio ou eliminação de dados desnecessários (IV) | O cadastro já coleta só o necessário. | Rotina de anonimização descrita abaixo. |
| Portabilidade (V) | Não há rota. | Exportar os dados em JSON pela mesma rota `GET /me/dados`. |
| Eliminação dos dados tratados com consentimento (VI) | A revogação interrompe o uso. | Eliminar o extrato de pontos e o envio de marketing quando o titular pedir. |
| Informação sobre a possibilidade de não consentir (VIII) | O cadastro mostra fidelidade e marketing como opcionais, desmarcados. | Texto dos termos exibido no app. |
| Revogação do consentimento (IX) | `POST /me/consentimentos` com `concedido: false`. | Já atendido. |

## Anonimização (proposta)

Quando o titular encerrar a conta, ou quando acabarem os prazos de retenção, a rede executaria esta rotina, que **ainda não está implementada**:

1. **Cadastro:** o nome vira "Cliente removido", o e-mail vira `anonimizado-<id>@invalido.local`, a senha é trocada por um valor aleatório e a conta é desativada. O ID interno fica só para manter a integridade das chaves estrangeiras.
2. **Pedidos e pagamentos:** continuam guardados até o fim do prazo fiscal, ligados ao cadastro já anonimizado. Como os pedidos não têm outros identificadores (CPF, telefone, endereço), deixam de identificar a pessoa por meios razoáveis, que é o critério do art. 12.
3. **Consentimentos:** guardados até o fim do prazo de prova e depois eliminados.
4. **Pontos de fidelidade:** o extrato é eliminado.
5. **Auditoria:** os eventos continuam válidos, porque já não guardam e-mail nem nome, apenas o ID agora anonimizado. A própria anonimização fica registrada como `USUARIO_ANONIMIZADO`, sem dados pessoais.

Dados anonimizados deixam de ser dados pessoais (art. 12) e podem ser mantidos para uso exclusivo do controlador, por exemplo em estatísticas de vendas (art. 16, IV).

## Segurança (art. 46)

Implementado:

- **Senhas:** guardadas com hash Argon2, nunca em texto e nunca devolvidas pela API.
- **Login:** feito com token JWT que expira em 60 minutos. O segredo de assinatura vem da variável `JWT_SECRET`, fora do código.
- **Controle de acesso:** controle por perfil e por unidade. Um funcionário não vê nem altera pedidos de outra unidade, e IDs ou perfis enviados no corpo da requisição não concedem acesso.
- **Minimização nas respostas:**
  - os pedidos mostram só o ID do cliente, sem nome nem e-mail, inclusive para a cozinha;
  - a auditoria não guarda e-mail, senha nem token;
  - os erros não expõem detalhes internos.
- **Auditoria:** registro das operações relevantes por unidade, consultável só pelo gerente da unidade.
- **Registro de acesso a dados pessoais:** quando um funcionário consulta individualmente o pedido de um cliente identificado, a auditoria registra `DADOS_CLIENTE_CONSULTADOS`, com quem consultou e o perfil dele. A consulta da própria auditoria também fica registrada (`AUDITORIA_CONSULTADA`). A listagem de pedidos não gera registro, para a consulta periódica da cozinha não inflar a auditoria; nela, o pedido mostra só o ID do cliente.

Proposta para produção: HTTPS obrigatório, banco servidor com cópias de segurança criptografadas, gestão de segredos, limite de tentativas de login e monitoramento de acessos.

## Incidentes de segurança (art. 48)

Em caso de incidente que possa causar risco ou dano relevante aos titulares, a rede deve comunicar a Autoridade Nacional de Proteção de Dados (ANPD) e os titulares afetados. O Regulamento de Comunicação de Incidente de Segurança (Resolução CD/ANPD nº 15/2024) estabelece o prazo de 3 dias úteis. A auditoria da API ajuda a reconstruir o que aconteceu e quem foi afetado.
