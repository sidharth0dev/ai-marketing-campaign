"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import axios from "axios";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { useApi } from "@/context/ApiContext";

const API_URL = "http://127.0.0.1:8000";

export default function SignupPage() {
  const router = useRouter();
  const { authToken } = useApi();

  useEffect(() => {
    if (authToken) {
      router.replace("/");
    }
  }, [authToken, router]);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsLoading(true);
    const toastId = toast.loading("Creating your account...");

    try {
      await axios.post(`${API_URL}/users/`, {
        email,
        password,
      });

      toast.dismiss(toastId);
      toast.success("Account created! Please log in.");
      router.push("/login");
    } catch (error: any) {
      console.error("Signup failed", error);
      toast.dismiss(toastId);
      const message =
        error?.response?.data?.detail || "Sign up failed. Please try again.";
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-gradient-to-b from-slate-950 via-slate-950 to-slate-900 p-6">
      <Card className="w-full max-w-md border-white/20 bg-slate-900/60 shadow-2xl backdrop-blur-2xl">
        <CardHeader>
          <CardTitle className="text-3xl font-semibold text-white">
            Create an account
          </CardTitle>
          <CardDescription className="text-sm text-slate-200/70">
            Sign up to start generating and tracking AI-powered campaigns.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email" className="text-slate-200/80">
                Email
              </Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                disabled={isLoading}
                required
                className="bg-slate-950/40 text-slate-100 placeholder:text-slate-400"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="text-slate-200/80">
                Password
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={isLoading}
                required
                minLength={8}
                className="bg-slate-950/40 text-slate-100 placeholder:text-slate-400"
              />
              <p className="text-xs text-slate-300/70">
                Password must be at least 8 characters.
              </p>
            </div>
            <Button
              type="submit"
              className="w-full bg-gradient-to-r from-purple-500 via-pink-500 to-blue-500 text-white shadow-lg hover:shadow-purple-500/50"
              disabled={isLoading}
            >
              {isLoading ? "Creating account..." : "Sign up"}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-slate-300/70">
            Already have an account?{" "}
            <Link href="/login" className="text-pink-400 hover:text-pink-300">
              Log in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
