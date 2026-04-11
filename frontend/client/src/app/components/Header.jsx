import { Sparkles, Shield } from "lucide-react";

export default function Header() {
  return (
    <header className="border-b border-gray-700/50 bg-gray-900/50 backdrop-blur-sm sticky top-0 z-10">
      <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-blue-500/20 to-purple-500/20 rounded-lg">
            <Sparkles className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-gray-100">LocalScript</h1>
            <p className="text-xs text-gray-400 flex items-center gap-1">
              <Shield className="w-3 h-3" />
              Private & Secure
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 bg-green-500 rounded-full animate-pulse"></div>
          <span className="text-xs text-gray-400">Online</span>
        </div>
      </div>
    </header>
  );
}

