# Política de segurança

Este é um projeto de portfólio com **dados 100% fictícios**; ele não processa dados pessoais reais nem se destina a produção.
Mesmo assim, relatos de problemas de segurança são bem-vindos.

## Como reportar

Use o recurso **Report a vulnerability** da aba *Security* deste repositório no GitHub (relato privado).
Evite abrir uma issue pública com detalhes de uma falha antes de ela ser corrigida.

## Boas práticas já adotadas

- Credenciais apenas em variáveis de ambiente (`.env`, ignorado pelo Git); o `.env.example` não tem valores reais.
- Consultas SQL estáticas ou parametrizadas, sem concatenação de dados externos.
- Operações que apagam dados pedem confirmação (ou `--yes`) e os testes de integração só aceitam bancos terminados em `_test`.
- Dependências monitoradas pelo Dependabot e pelo `pip-audit` (CI).
- Análise estática com Bandit e testes automáticos a cada alteração (GitHub Actions, com permissão mínima e ações fixadas por hash).

## Uso do código

Se você usar este código com um banco que contenha dados reais, crie um usuário dedicado com o mínimo de privilégios,
revise as travas acima e **não** reutilize as senhas de exemplo.
