import {
  createContext,
  useCallback,
  useContext,
  useState,
} from "react";

const StateContext = createContext(null);

const initialState = {
  user_query: "",
  agents: [],
  responses: [],
};

export function StateProvider({ children }) {
  const [state, setState] = useState(initialState);
  const [messages, setMessages] = useState([]);
  const [stateVisible, setStateVisible] = useState(true);
  const [loading, setLoading] = useState(false);

  // Substitui o estado completo recebido do AG-UI.
  // Utilizar quando receber STATE_SNAPSHOT.
  const updateState = useCallback((newState) => {
    if (!newState || typeof newState !== "object") {
      return;
    }

    setState({
      ...initialState,
      ...newState,
    });
  }, []);

  // Atualiza somente os campos informados.
  // Útil para atualizações locais.
  const patchState = useCallback((partialState) => {
    if (!partialState || typeof partialState !== "object") {
      return;
    }

    setState((prev) => ({
      ...prev,
      ...partialState,
    }));
  }, []);

  const resetState = useCallback(() => {
    setState(initialState);
  }, []);

  return (
    <StateContext.Provider
      value={{
        state,
        setState,
        updateState,
        patchState,
        resetState,

        messages,
        setMessages,

        stateVisible,
        setStateVisible,

        loading,
        setLoading,
      }}
    >
      {children}
    </StateContext.Provider>
  );
}

export function useAppState() {
  const context = useContext(StateContext);

  if (!context) {
    throw new Error(
      "useAppState deve ser utilizado dentro de StateProvider",
    );
  }

  return context;
}
