import { Component, type ErrorInfo, type ReactNode } from "react"
import { AlertCircle, RotateCcw } from "lucide-react"
import { Button } from "./ui"

interface Props {
  children: ReactNode
  fallbackTitle?: string
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  }

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error inside ErrorBoundary:", error, errorInfo)
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center p-8 md:p-12 text-center rounded-2xl border border-red-500/20 bg-red-500/5 dark:bg-red-950/20 my-6 max-w-xl mx-auto space-y-4">
          <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center text-red-500">
            <AlertCircle className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-foreground">
              {this.props.fallbackTitle || "Something went wrong loading this section"}
            </h3>
            <p className="text-xs text-muted-foreground font-mono">
              {this.state.error?.message || "An unexpected error occurred."}
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={this.handleReset}
            className="flex items-center gap-2"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Try Again</span>
          </Button>
        </div>
      )
    }

    return this.props.children
  }
}
