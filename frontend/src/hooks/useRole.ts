export type UserRole = "ADMIN" | "OPERATOR" | "VIEWER";

const ROLE = (import.meta.env.VITE_USER_ROLE as UserRole) || "VIEWER";

export function useRole() {
  const canEdit = ROLE !== "VIEWER";
  const canDelete = ROLE === "ADMIN";
  const canRunPipeline = ROLE !== "VIEWER";

  return {
    role: ROLE,
    canEdit,
    canDelete,
    canRunPipeline,
  };
}
