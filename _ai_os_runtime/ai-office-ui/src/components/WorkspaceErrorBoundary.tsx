import { AlertTriangle, RefreshCw } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  workspace: string;
}

interface State {
  error: Error | null;
}

export default class WorkspaceErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("AI Office workspace render failure", { error, errorInfo, workspace: this.props.workspace });
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <section className="workspace-error-boundary" role="alert">
        <AlertTriangle size={24} aria-hidden="true" />
        <div><h2>{this.props.workspace} could not render</h2><p>{this.state.error.message || "An unexpected interface error occurred."}</p></div>
        <button onClick={() => window.location.reload()} type="button"><RefreshCw size={14} aria-hidden="true" />Reload workspace</button>
      </section>
    );
  }
}
