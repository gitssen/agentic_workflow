"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function MusicRedirect() {
  const router = useRouter();
  
  useEffect(() => {
    // Redirect to the unified workspace on the home page
    router.replace("/");
  }, [router]);

  return null;
}
