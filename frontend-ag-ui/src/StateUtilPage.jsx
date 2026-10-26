import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion, AnimatePresence } from "framer-motion";

import { useAppState } from "./StateContext";
import AppLayout from "./Layout";

const cardVariants = {
  hidden: {
    opacity: 0,
    y: 15,
  },
  visible: {
    opacity: 1,
    y: 0,
  },
};

// --------------------------------------------------
// SEGURANÇA
// --------------------------------------------------

function maskCPF(cpf) {
  if (!cpf) return "";

  const digits = String(cpf).replace(/\D/g, "");

  if (digits.length !== 11) {
    return "***.***.***-**";
  }

  return `***.***.${digits.slice(6, 9)}-**`;
}

function maskCardNumber(number) {
  if (!number) return "**** **** **** ****";

  const digits = String(number).replace(/\D/g, "");

  if (digits.length < 4) {
    return "****";
  }

  return `**** **** **** ${digits.slice(-4)}`;
}

function sanitizeMessage(message) {
  if (typeof message !== "string") {
    return "";
  }

  return message
    // CPF formatado
    .replace(
      /\b\d{3}\.\d{3}\.\d{3}-\d{2}\b/g,
      (cpf) => maskCPF(cpf),
    )
    // CPF após rótulo
    .replace(
      /\b(CPF\s*:\s*)(\d{11})\b/gi,
      (_, label, cpf) => `${label}${maskCPF(cpf)}`,
    )
    // Cartão após rótulo
    .replace(
      /\b((?:número\s+do\s+)?cartão\s*:\s*)([\d -]{13,23})/gi,
      (_, label, number) =>
        `${label}${maskCardNumber(number)}`,
    );
}

// --------------------------------------------------
// NORMALIZAÇÃO DAS RESPOSTAS
// --------------------------------------------------

function normalizeResponses(responses) {
  if (!Array.isArray(responses)) {
    return [];
  }

  return responses.flatMap((item, index) => {
    if (typeof item === "string") {
      return [
        {
          id: `response-${index}`,
          agent: "supervisor",
          message: item,
          data: null,
        },
      ];
    }

    if (!item || typeof item !== "object") {
      return [];
    }

    // Formato atual do supervisor AG-UI:
    // { agent: "abrir_conta", response: "..." }
    if ("agent" in item && "response" in item) {
      const response = item.response;

      return [
        {
          id: `response-${index}`,
          agent: String(item.agent || "supervisor"),
          message:
            typeof response === "string"
              ? response
              : JSON.stringify(response, null, 2),
          data:
            response &&
            typeof response === "object" &&
            !Array.isArray(response)
              ? response
              : null,
        },
      ];
    }

    // Compatibilidade com o formato antigo:
    // { abrir_conta: "..." }
    return Object.entries(item).map(([agent, value], i) => ({
      id: `response-${index}-${i}`,
      agent,
      message:
        typeof value === "string"
          ? value
          : JSON.stringify(value, null, 2),
      data:
        value && typeof value === "object"
          ? value
          : null,
    }));
  });
}

// --------------------------------------------------
// NOMES DOS AGENTES
// --------------------------------------------------

function getAgentName(agent) {
  const names = {
    abrir_conta: "Abertura de Conta",
    cartao_credito: "Cartão de Crédito",
    supervisor: "Supervisor",
  };

  return names[agent] || agent;
}

// --------------------------------------------------
// BADGES
// --------------------------------------------------

function InfoBadge({ label, value }) {
  return (
    <div className="rounded-xl bg-gray-800 border border-gray-700 px-4 py-3">
      <p className="text-xs text-gray-400 mb-1">{label}</p>

      <p className="text-sm font-medium text-white break-words">
        {value}
      </p>
    </div>
  );
}

// --------------------------------------------------
// INFORMAÇÕES ESTRUTURADAS
// --------------------------------------------------

function StructuredData({ data }) {
  if (!data || typeof data !== "object") {
    return null;
  }

  const nome = data.nome || data.Nome;

  const cpf = data.cpf || data.CPF;

  const numeroConta =
    data.numero_conta ||
    data.numeroConta ||
    data.Conta;

  const saldo = data.saldo ?? data.Saldo;

  const tipoCartao =
    data.tipo_cartao ||
    data.CartaoTipo;

  const numeroCartao =
    data.numero_cartao ||
    data.CartaoNumero;

  const limite =
    data.limite ??
    data.CartaoLimite;

  const hasData = [
    nome,
    cpf,
    numeroConta,
    saldo,
    tipoCartao,
    numeroCartao,
    limite,
  ].some(
    (value) =>
      value !== null &&
      value !== undefined &&
      value !== "",
  );

  if (!hasData) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
      {nome && (
        <InfoBadge
          label="Nome"
          value={nome}
        />
      )}

      {cpf && (
        <InfoBadge
          label="CPF"
          value={maskCPF(cpf)}
        />
      )}

      {numeroConta && (
        <InfoBadge
          label="Conta"
          value={String(numeroConta)}
        />
      )}

      {saldo !== undefined && saldo !== null && (
        <InfoBadge
          label="Saldo"
          value={String(saldo)}
        />
      )}

      {tipoCartao && (
        <InfoBadge
          label="Tipo de cartão"
          value={tipoCartao}
        />
      )}

      {numeroCartao && (
        <InfoBadge
          label="Número do cartão"
          value={maskCardNumber(numeroCartao)}
        />
      )}

      {limite !== undefined && limite !== null && (
        <InfoBadge
          label="Limite"
          value={String(limite)}
        />
      )}
    </div>
  );
}

// --------------------------------------------------
// COMPONENTE PRINCIPAL
// --------------------------------------------------

export default function StateUtilPage() {
  const context = useAppState();

  const state = context?.state || {};

  const responses = useMemo(
    () => normalizeResponses(state.responses),
    [state.responses],
  );

  const agents = Array.isArray(state.agents)
    ? state.agents
    : [];

  const hasState = Object.keys(state).length > 0;

  return (
    <AppLayout>
      <div className="flex-1 min-h-0 overflow-y-auto bg-gray-900 p-6 text-white">
        <div className="max-w-5xl mx-auto space-y-6">

          {/* CABEÇALHO */}

          <div>
            <h1 className="text-3xl font-bold">
              📋 Estado Compartilhado
            </h1>

            <p className="text-gray-400 mt-2">
              Acompanhe os dados compartilhados entre
              o supervisor e os agentes do MDBank.
            </p>
          </div>

          {/* RESUMO */}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

            <InfoBadge
              label="Agentes selecionados"
              value={agents.length}
            />

            <InfoBadge
              label="Respostas recebidas"
              value={responses.length}
            />

            <InfoBadge
              label="Estado"
              value={
                hasState
                  ? "Disponível"
                  : "Aguardando atualização"
              }
            />

          </div>

          {/* SOLICITAÇÃO ORIGINAL */}

          {state.user_query && (
            <div className="rounded-2xl bg-gray-800 border border-gray-700 p-5">
              <h2 className="font-semibold mb-2">
                Solicitação do usuário
              </h2>

              <p className="text-gray-300">
                {sanitizeMessage(state.user_query)}
              </p>
            </div>
          )}

          {/* AGENTES */}

          {agents.length > 0 && (
            <div className="rounded-2xl bg-gray-800 border border-gray-700 p-5">
              <h2 className="font-semibold mb-4">
                Agentes envolvidos
              </h2>

              <div className="flex flex-wrap gap-2">
                {agents.map((agent) => (
                  <span
                    key={agent}
                    className="rounded-full bg-blue-600/20 text-blue-300 border border-blue-500/30 px-4 py-2 text-sm"
                  >
                    {getAgentName(agent)}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* RESPOSTAS */}

          <div>
            <h2 className="text-xl font-semibold mb-4">
              Histórico de Respostas
            </h2>

            {responses.length === 0 ? (
              <div className="rounded-2xl bg-gray-800 border border-gray-700 p-8 text-center">
                <p className="text-gray-400">
                  Nenhuma resposta registrada ainda.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <AnimatePresence initial={false}>
                  {responses.map((response) => (
                    <motion.div
                      key={response.id}
                      variants={cardVariants}
                      initial="hidden"
                      animate="visible"
                      exit="hidden"
                      transition={{ duration: 0.3 }}
                      className="rounded-2xl bg-gray-800 border border-gray-700 p-5 shadow-lg"
                    >

                      {/* IDENTIFICAÇÃO */}

                      <div className="flex items-center justify-between mb-4">
                        <span className="text-sm font-semibold text-blue-300">
                          🤖 {getAgentName(response.agent)}
                        </span>

                        <span className="text-xs text-green-400">
                          Resposta recebida
                        </span>
                      </div>

                      {/* MENSAGEM */}

                      <div className="prose prose-invert max-w-none text-gray-100">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                        >
                          {sanitizeMessage(response.message)}
                        </ReactMarkdown>
                      </div>

                      {/* DADOS ESTRUTURADOS */}

                      <StructuredData data={response.data} />

                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            )}
          </div>

          {/* JSON DO ESTADO */}

          <div className="rounded-2xl bg-gray-950 border border-gray-700 overflow-hidden">
            <div className="px-5 py-4 border-b border-gray-700">
              <h2 className="font-semibold">
                Estado AG-UI
              </h2>

              <p className="text-xs text-gray-400 mt-1">
                Visualização de diagnóstico
              </p>
            </div>

            <pre className="p-5 overflow-x-auto text-xs text-green-400">
              {JSON.stringify(
                {
                  user_query: sanitizeMessage(
                    state.user_query || "",
                  ),
                  agents,
                  response_count: responses.length,
                  responses: responses.map((item) => ({
                    agent: item.agent,
                    message: sanitizeMessage(item.message),
                  })),
                },
                null,
                2,
              )}
            </pre>
          </div>

        </div>
      </div>
    </AppLayout>
  );
}
