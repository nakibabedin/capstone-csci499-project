import { createClient } from "@supabase/supabase-js";

// Local development without Supabase: everyone is a fake "dev" user and no
// login is needed. The backend must also have DISABLE_SUPABASE=true.
export const supabaseDisabled =
  import.meta.env.VITE_DISABLE_SUPABASE === "true";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabasePublishableKey =
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

if (!supabaseDisabled && (!supabaseUrl || !supabasePublishableKey)) {
  throw new Error(
    "Supabase environment variables are missing from frontend/.env " +
      "(set VITE_DISABLE_SUPABASE=true to develop without them).",
  );
}

// With Supabase disabled the client gets placeholders. It is never used to
// sign in, and with no stored session it makes no network requests.
export const supabase = createClient(
  supabaseUrl || "http://localhost",
  supabasePublishableKey || "disabled",
);

/** Headers with the signed-in user's token added, for calls to the Flask API. */
export async function authHeaders(init?: HeadersInit): Promise<Headers> {
  const headers = new Headers(init);
  const { data } = await supabase.auth.getSession();
  if (data.session?.access_token) {
    headers.set("Authorization", `Bearer ${data.session.access_token}`);
  }
  return headers;
}
