import { useState, useRef, useEffect } from "react";
import { Bot, ChevronDown, ChevronRight, Folder, FolderPlus, LogOut, MessageSquare, MoreHorizontal, Plus, Settings, Trash2, X } from "lucide-react";
import { Link } from "react-router-dom";

import type { Conversation, ConversationFolder } from "@/lib/api";
import { useAuth } from "@/stores/auth";

const FOLDER_COLORS = [
  "#ef4444",
  "#f97316",
  "#eab308",
  "#22c55e",
  "#06b6d4",
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
  "#f43f5e",
];

interface SidebarProps {
  conversations: Conversation[];
  folders: ConversationFolder[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onCreateFolder: (name: string, color: string | null) => void;
  onDeleteFolder: (id: string) => void;
  onMoveConversation: (conversationId: string, folderId: string | null) => void;
}

export default function Sidebar({
  conversations,
  folders,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onCreateFolder,
  onDeleteFolder,
  onMoveConversation,
}: SidebarProps) {
  const { user, logout, isAdmin } = useAuth();
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [newFolderColor, setNewFolderColor] = useState<string | null>(FOLDER_COLORS[5]);
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [moveMenuOpen, setMoveMenuOpen] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(null);
        setMoveMenuOpen(null);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const toggleFolder = (id: string) => {
    setExpandedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const unfiled = conversations.filter((c) => !c.folder_id);
  const byFolder = (folderId: string) => conversations.filter((c) => c.folder_id === folderId);

  const handleCreateFolder = () => {
    const name = newFolderName.trim();
    if (!name) return;
    onCreateFolder(name, newFolderColor);
    setNewFolderName("");
    setCreatingFolder(false);
    setNewFolderColor(FOLDER_COLORS[5]);
  };

  const ConversationItem = ({ c }: { c: Conversation }) => (
    <div
      key={c.id}
      className={`group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition ${
        c.id === activeId
          ? "bg-zinc-800/80 text-zinc-100"
          : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
      }`}
      onClick={() => onSelect(c.id)}
    >
      <MessageSquare className="h-3.5 w-3.5 shrink-0 text-zinc-500" />
      <span className="flex-1 truncate">{c.title ?? "New conversation"}</span>
      <div className="relative">
        <button
          onClick={(e) => {
            e.stopPropagation();
            setMenuOpen(menuOpen === c.id ? null : c.id);
            setMoveMenuOpen(null);
          }}
          className="hidden shrink-0 rounded p-1 text-zinc-500 hover:text-zinc-200 group-hover:block"
          aria-label="Conversation options"
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </button>
        {menuOpen === c.id && (
          <div
            ref={menuRef}
            className="absolute right-0 top-6 z-50 w-40 rounded-lg border border-zinc-700 bg-zinc-900 py-1 shadow-xl"
          >
            <button
              onClick={(e) => {
                e.stopPropagation();
                setMoveMenuOpen(c.id);
                setMenuOpen(null);
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-zinc-300 hover:bg-zinc-800"
            >
              <Folder className="h-3.5 w-3.5" />
              Move to folder…
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete(c.id);
                setMenuOpen(null);
              }}
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-red-400 hover:bg-zinc-800"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete
            </button>
          </div>
        )}
        {moveMenuOpen === c.id && (
          <div
            ref={menuRef}
            className="absolute right-0 top-6 z-50 w-44 rounded-lg border border-zinc-700 bg-zinc-900 py-1 shadow-xl"
          >
            {folders.length === 0 && (
              <p className="px-3 py-2 text-xs text-zinc-500">No folders yet</p>
            )}
            {c.folder_id && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onMoveConversation(c.id, null);
                  setMoveMenuOpen(null);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-zinc-300 hover:bg-zinc-800"
              >
                <MessageSquare className="h-3.5 w-3.5" />
                Unfiled
              </button>
            )}
            {folders.map((f) => (
              <button
                key={f.id}
                onClick={(e) => {
                  e.stopPropagation();
                  onMoveConversation(c.id, f.id);
                  setMoveMenuOpen(null);
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-zinc-300 hover:bg-zinc-800"
              >
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: f.color ?? "#3b82f6" }}
                />
                {f.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-zinc-800/70 bg-zinc-950">
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/20">
          <Bot className="h-4 w-4 text-white" />
        </div>
        <span className="text-sm font-semibold tracking-tight text-zinc-100">
          Company Platform
        </span>
      </div>

      <div className="px-3">
        <button
          onClick={onNew}
          className="flex w-full items-center gap-2 rounded-xl border border-zinc-700/80 bg-zinc-900/60 px-3 py-2.5 text-sm font-medium text-zinc-300 transition hover:bg-zinc-800/80 hover:text-zinc-100 hover:border-zinc-600"
        >
          <Plus className="h-4 w-4" />
          New chat
        </button>
      </div>

      <nav className="mt-3 flex-1 space-y-1 overflow-y-auto px-3 pb-4">
        {/* New folder button / form */}
        {!creatingFolder ? (
          <button
            onClick={() => setCreatingFolder(true)}
            className="mb-1 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-medium text-zinc-500 transition hover:bg-zinc-900 hover:text-zinc-300"
          >
            <FolderPlus className="h-3.5 w-3.5" />
            New folder
          </button>
        ) : (
          <div className="mb-2 rounded-lg border border-zinc-700/60 bg-zinc-900/60 p-2">
            <div className="flex items-center gap-2">
              <input
                autoFocus
                type="text"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreateFolder();
                  if (e.key === "Escape") {
                    setCreatingFolder(false);
                    setNewFolderName("");
                  }
                }}
                placeholder="Folder name…"
                className="flex-1 rounded-md bg-zinc-800 px-2 py-1 text-xs text-zinc-200 placeholder-zinc-600 outline-none ring-1 ring-zinc-700 focus:ring-indigo-500"
              />
              <button
                onClick={() => {
                  setCreatingFolder(false);
                  setNewFolderName("");
                }}
                className="rounded p-1 text-zinc-500 hover:text-zinc-300"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {FOLDER_COLORS.map((c) => (
                <button
                  key={c}
                  onClick={() => setNewFolderColor(c)}
                  className={`h-5 w-5 rounded-full transition ${newFolderColor === c ? "ring-2 ring-white" : ""}`}
                  style={{ backgroundColor: c }}
                />
              ))}
            </div>
            <button
              onClick={handleCreateFolder}
              disabled={!newFolderName.trim()}
              className="mt-2 w-full rounded-md bg-indigo-600 px-2 py-1 text-xs font-medium text-white transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Create folder
            </button>
          </div>
        )}

        {/* Unfiled conversations */}
        {unfiled.length > 0 && (
          <div className="space-y-0.5">
            {unfiled.map((c) => (
              <ConversationItem key={c.id} c={c} />
            ))}
          </div>
        )}

        {/* Folders */}
        {folders.map((folder) => {
          const items = byFolder(folder.id);
          const isExpanded = expandedFolders.has(folder.id);
          return (
            <div key={folder.id} className="pt-1">
              <div className="group flex items-center gap-1.5 px-2 py-1">
                <button
                  onClick={() => toggleFolder(folder.id)}
                  className="flex items-center gap-1.5 text-xs font-medium text-zinc-500 transition hover:text-zinc-300"
                >
                  {isExpanded ? (
                    <ChevronDown className="h-3.5 w-3.5" />
                  ) : (
                    <ChevronRight className="h-3.5 w-3.5" />
                  )}
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ backgroundColor: folder.color ?? "#3b82f6" }}
                  />
                  <span className="truncate">{folder.name}</span>
                  <span className="text-zinc-600">({items.length})</span>
                </button>
                <button
                  onClick={() => onDeleteFolder(folder.id)}
                  className="ml-auto hidden rounded p-0.5 text-zinc-600 hover:text-red-400 group-hover:block"
                  aria-label="Delete folder"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
              {isExpanded && (
                <div className="ml-4 space-y-0.5 border-l border-zinc-800/60 pl-2">
                  {items.length === 0 && (
                    <p className="px-3 py-2 text-xs text-zinc-600">Empty folder</p>
                  )}
                  {items.map((c) => (
                    <ConversationItem key={c.id} c={c} />
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {conversations.length === 0 && folders.length === 0 && (
          <div className="px-3 py-8 text-center">
            <MessageSquare className="mx-auto mb-2 h-5 w-5 text-zinc-700" />
            <p className="text-xs text-zinc-600">No conversations yet</p>
          </div>
        )}
      </nav>

      {isAdmin() && (
        <div className="px-3 py-2 border-t border-zinc-800/50">
          <Link
            to="/admin"
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200 transition"
          >
            <Settings className="h-4 w-4" />
            Admin Panel
          </Link>
        </div>
      )}
      <div className="flex items-center gap-2.5 border-t border-zinc-800/50 px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-zinc-700 to-zinc-600 text-xs font-semibold uppercase text-zinc-200 ring-2 ring-zinc-800">
          {user?.email[0] ?? "?"}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-medium text-zinc-300">{user?.email}</p>
          <p className="text-[10px] uppercase tracking-wide text-zinc-500">
            {user?.role}
          </p>
        </div>
        <button
          onClick={logout}
          className="rounded-md p-1 text-zinc-500 transition hover:bg-zinc-800 hover:text-zinc-200"
          aria-label="Log out"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </aside>
  );
}
