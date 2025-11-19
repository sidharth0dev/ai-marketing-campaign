"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useApi } from "@/context/ApiContext";
import { toast } from "sonner";
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
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  BarChart3,
  CalendarClock,
  Copy,
  Download,
  FolderOpen,
  Loader2,
  LogOut,
  Plus,
  RefreshCw,
  Package,
  Eye,
  CheckCircle2,
  Trash,
} from "lucide-react";
import { motion } from "framer-motion";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

type GeneratedText = {
  id: number;
  platform: string;
  caption: string;
  persuasiveness_score: number | null;
  clarity_score: number | null;
  feedback: string | null;
};

type GeneratedImage = {
  id: number;
  platform: string;
  image_url: string;
  image_prompt: string;
  original_image_url?: string | null;
  variation_number?: number | null;
  is_selected?: boolean;
  tags?: string[] | null;
  collection?: string | null;
};

type CampaignDetails = {
  id: number;
  product_name: string;
  product_url: string;
  created_at: string;
  texts: GeneratedText[];
  images: GeneratedImage[];
};

type CampaignSummary = {
  id: number;
  product_name: string;
  product_url: string;
  created_at: string;
  preview_image_url?: string | null;
};

const formatDate = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString();
};

const formatTime = (value: string | null) => {
  if (!value) return "No campaigns yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
};

const scoreColor = (score: number | null) => {
  if (score === null || score === undefined) return "text-slate-200";
  if (score >= 8) return "text-emerald-400";
  if (score >= 5) return "text-yellow-400";
  return "text-rose-400";
};

const resolveAssetUrl = (path?: string | null) => {
  if (!path) return "";
  return path.startsWith("http") ? path : `${API_URL}${path}`;
};

export default function DashboardPage() {
  const router = useRouter();
  const { authToken, api, logout } = useApi();

  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [activeCampaign, setActiveCampaign] = useState<CampaignDetails | null>(null);
  const [isFetchingCampaign, setIsFetchingCampaign] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);

  const [url, setUrl] = useState(
    "https://www.amazon.com/SAMSUNG-Unlocked-Smartphone-Charging-Expandable/dp/B0DLHNWHRF/"
  );
  const [productName, setProductName] = useState<string>("");
  const [productImage, setProductImage] = useState<File | null>(null);
  const [enableABTesting, setEnableABTesting] = useState(false);
  const [numVariations, setNumVariations] = useState(2);

  useEffect(() => {
    if (!authToken) {
      router.replace("/login");
    }
  }, [authToken, router]);

  const fetchCampaigns = async () => {
    try {
      const response = await api.get<CampaignSummary[]>("/api/v1/campaigns/");
      setCampaigns(response.data);
    } catch (error) {
      console.error("Failed to fetch campaigns", error);
      toast.error("Unable to load campaigns.");
    }
  };

  const fetchCampaignDetails = async (campaignId: number) => {
    setIsFetchingCampaign(true);
    try {
      const response = await api.get<CampaignDetails>(
        `/api/v1/campaigns/${campaignId}`
      );
      setActiveCampaign(response.data);
    } catch (error) {
      console.error("Failed to fetch campaign details", error);
      toast.error("Unable to load campaign details.");
    } finally {
      setIsFetchingCampaign(false);
    }
  };

  useEffect(() => {
    if (authToken) {
      fetchCampaigns();
    }
  }, [authToken]);

  const stats = useMemo(() => {
    const totalCampaigns = campaigns.length;
    const lastRun = campaigns[0]?.created_at ?? null;
    const totalImages = activeCampaign?.images.length ?? 0;
    return {
      totalCampaigns,
      totalImages,
      lastRun,
    };
  }, [campaigns, activeCampaign]);

  const findImage = (platform: string, variationNumber: number = 0) => {
    return activeCampaign?.images.find(
      (img) => img.platform === platform && (img.variation_number ?? 0) === variationNumber
    );
  };

  const findImagesByPlatform = (platform: string) => {
    return activeCampaign?.images.filter((img) => img.platform === platform) || [];
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Caption copied to clipboard!");
  };

  const handleDownload = async (imageUrl: string) => {
    try {
      const assetUrl = resolveAssetUrl(imageUrl);
      const response = await fetch(assetUrl);
      if (!response.ok) {
        throw new Error("Failed to fetch image");
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      // Extract filename from URL or use default
      const filename = imageUrl.split("/").pop() || "campaign-image.png";
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      toast.success("Image downloaded successfully!");
    } catch (error) {
      console.error("Download failed", error);
      toast.error("Failed to download image. Please try again.");
    }
  };

  const handleBatchExport = async (campaignId: number) => {
    try {
      const response = await fetch(`${API_URL}/api/v1/assets/export/${campaignId}`, {
        headers: {
          Authorization: `Bearer ${authToken}`,
        },
      });
      if (!response.ok) {
        throw new Error("Failed to export assets");
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${activeCampaign?.product_name || "campaign"}_assets.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      toast.success("Assets exported successfully!");
    } catch (error) {
      console.error("Export failed", error);
      toast.error("Failed to export assets. Please try again.");
    }
  };


  const handleDeleteCampaign = async (campaignId: number) => {
    if (!window.confirm("Are you sure you want to delete this campaign?")) {
      return false;
    }

    try {
      await api.delete(`/campaigns/${campaignId}`);
      setCampaigns((prev) => prev.filter((campaign) => campaign.id !== campaignId));
      if (activeCampaign?.id === campaignId) {
        setActiveCampaign(null);
      }
      toast.success("Campaign deleted");
      return true;
    } catch (error: any) {
      console.error("Failed to delete campaign", error);
      const message = error?.response?.data?.detail || "Unable to delete campaign.";
      toast.error(message);
      return false;
    }
  };


  const handleDeleteActiveCampaign = async () => {
    if (!activeCampaign) return;
    const success = await handleDeleteCampaign(activeCampaign.id);
    if (success) {
      router.push("/");
    }
  };

  const handleRegenerateImage = async (campaignId: number, platform: string, variationNumber: number = 0) => {
    try {
      const toastId = toast.loading(`Regenerating image for ${platform}...`);
      const response = await api.post("/api/v1/assets/regenerate", {
        campaign_id: campaignId,
        platform,
        variation_number: variationNumber,
      });
      toast.dismiss(toastId);
      toast.success("Image regenerated!");
      // Refresh campaign details
      await fetchCampaignDetails(campaignId);
    } catch (error: any) {
      console.error("Regeneration failed", error);
      toast.error(error?.response?.data?.detail || "Failed to regenerate image.");
    }
  };

  const handleSelectABWinner = async (imageId: number, isSelected: boolean) => {
    try {
      await api.post("/api/v1/assets/ab-test/select", {
        image_id: imageId,
        is_selected: isSelected,
      });
      toast.success(isSelected ? "Image selected as winner!" : "Selection removed");
      if (activeCampaign) {
        await fetchCampaignDetails(activeCampaign.id);
      }
    } catch (error: any) {
      console.error("Selection failed", error);
      toast.error(error?.response?.data?.detail || "Failed to update selection.");
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsGenerating(true);
    const toastId = toast.loading(
      "Generating campaign... This may take a couple of minutes."
    );

    try {
      const formData = new FormData();
      formData.append("product_url", url);
      if (productName.trim()) {
        formData.append("product_name", productName.trim());
      }
      if (productImage) {
        formData.append("product_image", productImage);
      }
      formData.append("enable_ab_testing", enableABTesting.toString());
      formData.append("num_variations", numVariations.toString());

      const response = await api.post<CampaignDetails>(
        "/api/v1/generate/campaign",
        formData,
        {
          headers: { "Content-Type": "multipart/form-data" },
        }
      );

      toast.dismiss(toastId);
      toast.success("Campaign generated!");
      setActiveCampaign(response.data);
      fetchCampaigns();
    } catch (error: any) {
      console.error("Generation failed", error);
      toast.dismiss(toastId);
      const message =
        error?.response?.data?.detail || "Generation failed. Please try again.";
      toast.error(message);
    } finally {
      setIsGenerating(false);
    }
  };

  if (!authToken) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-950 to-slate-900 p-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <header className="flex flex-col gap-4 border-b pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-50">
              Campaign Studio
            </h1>
            <p className="text-sm text-slate-200">
              Welcome back! You’re ready to generate, analyze, and manage your AI campaigns.
            </p>
          </div>
          <Button
            variant="ghost"
            onClick={logout}
            className="rounded-full border border-white/30 bg-white/10 px-6 text-slate-50 shadow-lg transition-all duration-200 hover:scale-105 hover:bg-white/20 hover:text-white"
          >
            <LogOut className="mr-2 h-4 w-4" />
            Logout
          </Button>
        </header>

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card className="transition-transform duration-300 hover:scale-[1.02] hover:border-white/30 hover:shadow-emerald-500/20">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardDescription className="text-slate-200">Total campaigns</CardDescription>
              <FolderOpen className="h-4 w-4 text-slate-300" />
            </CardHeader>
            <CardContent>
              <CardTitle className="text-4xl font-semibold text-blue-400">
                {stats.totalCampaigns}
              </CardTitle>
            </CardContent>
          </Card>
          <Card className="transition-transform duration-300 hover:scale-[1.02] hover:border-white/30 hover:shadow-emerald-500/20">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardDescription className="text-slate-200">Assets in current view</CardDescription>
              <BarChart3 className="h-4 w-4 text-slate-300" />
            </CardHeader>
            <CardContent>
              <CardTitle className="text-4xl font-semibold text-blue-400">
                {stats.totalImages}
              </CardTitle>
            </CardContent>
          </Card>
          <Card className="sm:col-span-2 lg:col-span-1 transition-transform duration-300 hover:scale-[1.02] hover:border-white/30 hover:shadow-emerald-500/20">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardDescription className="text-slate-200">Last generated</CardDescription>
              <CalendarClock className="h-4 w-4 text-slate-300" />
            </CardHeader>
            <CardContent>
              <CardTitle className="text-2xl font-semibold text-blue-300">
                {formatTime(stats.lastRun)}
              </CardTitle>
            </CardContent>
          </Card>
        </section>

        <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
          <Card className="h-full transition-transform duration-300 hover:scale-[1.02] hover:border-white/30 hover:shadow-emerald-500/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg text-white">Your campaigns</CardTitle>
              <CardDescription className="text-slate-200">
                Select a campaign to review its outputs or create a new one below.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              <Button
                className="mb-4 w-full"
                variant="secondary"
                onClick={() => {
                  const element = document.getElementById("new-campaign-form");
                  element?.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
              >
                <Plus className="mr-2 h-4 w-4" />
                New campaign
              </Button>
              <ScrollArea className="h-[420px] pr-2">
                <div className="space-y-2">
                  {campaigns.length === 0 && (
                    <p className="text-sm text-slate-300">
                      No campaigns yet. Generate your first campaign to see it here.
                    </p>
                  )}
                  {campaigns.map((campaign) => (
                    <button
                      key={campaign.id}
                      onClick={() => fetchCampaignDetails(campaign.id)}
                      className={`w-full rounded-md border p-3 text-left transition-all duration-300 hover:border-primary hover:bg-primary/10 hover:shadow-lg hover:shadow-pink-500/10 hover:scale-[1.02] ${
                        activeCampaign?.id === campaign.id
                          ? "border-primary bg-primary/10"
                          : "border-border"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <h3 className="font-medium text-slate-100">{campaign.product_name}</h3>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-slate-300">
                            {formatDate(campaign.created_at)}
                          </span>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleDeleteCampaign(campaign.id);
                            }}
                            className="rounded-full p-1 text-red-500 transition-colors hover:text-red-700"
                            title="Delete campaign"
                          >
                            <Trash className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                      <p className="mt-1 truncate text-xs text-slate-300">
                        {campaign.product_url}
                      </p>
                    </button>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card
              id="new-campaign-form"
              className="transition-transform duration-300 hover:scale-[1.02] hover:border-white/30 hover:shadow-emerald-500/20"
            >
              <CardHeader>
                <CardTitle className="text-white">Create a new campaign</CardTitle>
                <CardDescription className="text-slate-200">
                  Paste a product URL and optionally upload a product photo. The photo is
                  analyzed pixel-by-pixel to enrich the generated prompts.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="url">Product URL</Label>
                    <Input
                      id="url"
                      type="url"
                      value={url}
                      onChange={(event) => setUrl(event.target.value)}
                      disabled={isGenerating}
                      required
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="productName">Product name (optional)</Label>
                    <Input
                      id="productName"
                      type="text"
                      value={productName}
                      onChange={(event) => setProductName(event.target.value)}
                      disabled={isGenerating}
                      placeholder="Leave empty to auto-detect from the URL"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="productImage">Product image (optional)</Label>
                    <Input
                      id="productImage"
                      type="file"
                      accept="image/*"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) {
                          if (file.size > 10 * 1024 * 1024) {
                            toast.error("Image size must be less than 10MB");
                            setProductImage(null);
                            event.target.value = "";
                            return;
                          }
                          setProductImage(file);
                          toast.success(`Image selected: ${file.name}`);
                        } else {
                          setProductImage(null);
                        }
                      }}
                      disabled={isGenerating}
                    />
                    {productImage && (
                      <div className="flex items-center gap-2 text-sm text-slate-300">
                        <span>Selected: {productImage.name}</span>
                        <span>•</span>
                        <span>{(productImage.size / 1024).toFixed(1)} KB</span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setProductImage(null);
                            const fileInput = document.getElementById(
                              "productImage"
                            ) as HTMLInputElement | null;
                            if (fileInput) fileInput.value = "";
                          }}
                          className="ml-auto h-6 px-2 text-xs"
                        >
                          Remove
                        </Button>
                      </div>
                    )}
                    <p className="text-xs text-slate-300">
                      Uploaded images are analyzed to extract precise colors, textures, brand details, and feature highlights. The generation model uses these insights when creating prompts.
                    </p>
                  </div>

                  <div className="space-y-3 rounded-lg border border-white/10 bg-slate-800/30 p-4">
                    <div className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        id="enableABTesting"
                        checked={enableABTesting}
                        onChange={(e) => setEnableABTesting(e.target.checked)}
                        disabled={isGenerating}
                        className="h-4 w-4 rounded border-white/40 bg-slate-900/60 text-pink-400 focus:ring-white/40"
                      />
                      <Label htmlFor="enableABTesting" className="cursor-pointer font-medium">
                        Enable A/B Testing
                      </Label>
                    </div>
                    {enableABTesting && (
                      <div className="ml-6 space-y-2">
                        <Label htmlFor="numVariations" className="text-sm">
                          Number of variations per platform (2-3)
                        </Label>
                        <Input
                          id="numVariations"
                          type="number"
                          min="2"
                          max="3"
                          value={numVariations}
                          onChange={(e) => setNumVariations(parseInt(e.target.value) || 2)}
                          disabled={isGenerating}
                          className="w-24"
                        />
                        <p className="text-xs text-slate-300">
                          Generate multiple variations per platform to test which performs best.
                        </p>
                      </div>
                    )}
                  </div>

                  <Button type="submit" size="lg" disabled={isGenerating} className="w-full">
                    {isGenerating ? "Generating..." : "Generate campaign"}
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card className="transition-transform duration-300 hover:scale-[1.02] hover:border-white/30 hover:shadow-emerald-500/20">
              <CardHeader>
                <CardTitle className="flex items-center justify-between text-white">
                  Campaign preview
                  <div className="flex items-center gap-2">
                    {activeCampaign && (
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleBatchExport(activeCampaign.id)}
                          className="rounded-full border-white/20 bg-white/5 text-slate-100 shadow-md transition-all duration-200 hover:scale-105 hover:border-pink-400 hover:shadow-[0_0_25px_rgba(236,72,153,0.35)]"
                        >
                          <Package className="mr-2 h-4 w-4" />
                          Export All
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleDeleteActiveCampaign}
                          className="rounded-full border border-red-600 text-red-400 transition-all duration-200 hover:bg-red-600 hover:text-white"
                        >
                          Delete Campaign
                        </Button>
                      </div>
                    )}
                    {isFetchingCampaign && <Loader2 className="h-4 w-4 animate-spin" />}
                  </div>
                </CardTitle>
                <CardDescription className="text-slate-200">
                  {activeCampaign
                    ? `Generated on ${formatDate(activeCampaign.created_at)}`
                    : "Select a campaign or generate a new one to see the details."}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {activeCampaign ? (
                  <Tabs
                    defaultValue={activeCampaign.texts[0]?.platform ?? ""}
                    className="mt-4"
                  >
                    <TabsList className="flex flex-wrap gap-2 rounded-full bg-white/5 p-1 backdrop-blur">
                      {activeCampaign.texts.map((text) => (
                        <TabsTrigger
                          key={text.id}
                          value={text.platform}
                          className="rounded-full px-4 py-2 text-sm text-slate-300 transition-all duration-300 hover:bg-white/10 hover:text-white data-[state=active]:border-b-2 data-[state=active]:border-pink-400 data-[state=active]:bg-white data-[state=active]:text-gray-900 data-[state=active]:shadow-[0_0_25px_rgba(236,72,153,0.45)]"
                        >
                          {text.platform}
                        </TabsTrigger>
                      ))}
                    </TabsList>

                    {activeCampaign.texts.map((text) => {
                      const platformImages = findImagesByPlatform(text.platform);
                      const mainImage = findImage(text.platform, 0);
                      const hasVariations = platformImages.length > 1;

                      return (
                        <TabsContent key={text.id} value={text.platform} className="space-y-4">
                          <motion.div
                            key={`${activeCampaign.id}-${text.id}`}
                            initial={{ opacity: 0, y: 30 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ duration: 0.6, ease: "easeOut" }}
                            className="space-y-6"
                          >
                            {/* A/B Testing Variations */}
                            {hasVariations && (
                              <div className="rounded-lg border border-white/10 bg-slate-800/30 p-4">
                                <h3 className="mb-4 font-semibold">A/B Testing Variations</h3>
                                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                  {platformImages.map((img) => {
                                    const isSelected = img.is_selected ?? false;
                                    const isMain = (img.variation_number ?? 0) === 0;
                                    const fullImageUrl = resolveAssetUrl(img.image_url);
                                    const originalUrl = img.original_image_url
                                      ? `${API_URL}${img.original_image_url}`
                                      : null;

                                    return (
                                      <div
                                        key={img.id}
                                        className={`relative rounded-lg border-2 p-2 transition-all ${
                                          isSelected
                                            ? "border-pink-400 bg-pink-400/10 shadow-[0_0_25px_rgba(236,72,153,0.35)]"
                                            : "border-white/10 bg-slate-800/30"
                                        }`}
                                      >
                                        <div className="mb-2 flex items-center justify-between">
                                          <span className="text-xs font-semibold text-slate-100">
                                            {isMain ? "Main" : `Variation ${img.variation_number}`}
                                          </span>
                                          <button
                                            onClick={() => handleSelectABWinner(img.id, !isSelected)}
                                            className={`rounded-full p-1 transition-all ${
                                              isSelected
                                                ? "bg-pink-400/20 text-pink-400"
                                                : "bg-white/5 text-slate-400 hover:bg-white/10"
                                            }`}
                                            title={isSelected ? "Selected as winner" : "Select as winner"}
                                          >
                                            <CheckCircle2 className="h-4 w-4" />
                                          </button>
                                        </div>
                                        <img
                                          src={fullImageUrl}
                                          alt={`${text.platform} ${isMain ? "main" : `variation ${img.variation_number}`}`}
                                          className="mb-2 h-32 w-full rounded object-cover"
                                          onError={(event) => {
                                            const target = event.target as HTMLImageElement;
                                            target.src = `${API_URL}/static/images/default_error_image.png`;
                                          }}
                                        />
                                        <div className="flex gap-1">
                                          <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => handleDownload(img.image_url)}
                                            className="h-7 flex-1 text-xs text-slate-200 hover:text-white"
                                          >
                                            <Download className="h-3 w-3" />
                                          </Button>
                                          <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() =>
                                              handleRegenerateImage(
                                                activeCampaign.id,
                                                text.platform,
                                                img.variation_number ?? 0
                                              )
                                            }
                                            className="h-7 flex-1 text-xs text-slate-200 hover:text-white"
                                          >
                                            <RefreshCw className="h-3 w-3" />
                                          </Button>
                                          {originalUrl && (
                                            <Button
                                              variant="ghost"
                                              size="sm"
                                              onClick={() => {
                                                const comparisonWindow = window.open("", "_blank");
                                                if (comparisonWindow) {
                                                  comparisonWindow.document.write(`
                                                    <html>
                                                      <head><title>Image Comparison</title>
                                                      <style>
                                                        body { margin: 0; padding: 20px; background: #0f172a; color: white; font-family: sans-serif; }
                                                        .container { display: flex; gap: 20px; height: 90vh; }
                                                        .image-container { flex: 1; display: flex; flex-direction: column; }
                                                        .image-container h3 { margin-bottom: 10px; }
                                                        img { width: 100%; height: auto; border: 2px solid rgba(255,255,255,0.1); border-radius: 8px; }
                                                      </style>
                                                      </head>
                                                      <body>
                                                        <h1>Image Comparison</h1>
                                                        <div class="container">
                                                          <div class="image-container">
                                                            <h3>Original</h3>
                                                            <img src="${originalUrl}" alt="Original" />
                                                          </div>
                                                          <div class="image-container">
                                                            <h3>Generated</h3>
                                                            <img src="${fullImageUrl}" alt="Generated" />
                                                          </div>
                                                        </div>
                                                      </body>
                                                    </html>
                                                  `);
                                                }
                                              }}
                                              className="h-7 flex-1 text-xs text-slate-200 hover:text-white"
                                              title="Compare with original"
                                            >
                                              <Eye className="h-3 w-3" />
                                            </Button>
                                          )}
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}

                            <div className="grid gap-6 lg:grid-cols-2">
                              <div className="flex flex-col space-y-4">
                                <div className="flex items-center justify-between">
                                  <h3 className="font-semibold text-slate-100">
                                    {hasVariations ? "Selected image" : "Generated image"}
                                  </h3>
                                  {mainImage && (
                                    <div className="flex gap-2">
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleDownload(mainImage.image_url)}
                                        className="rounded-full border-white/20 bg-white/5 text-slate-100 shadow-md transition-all duration-200 hover:scale-105 hover:border-pink-400 hover:shadow-[0_0_25px_rgba(236,72,153,0.35)]"
                                      >
                                        <Download className="mr-2 h-4 w-4" />
                                        Download
                                      </Button>
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() =>
                                          handleRegenerateImage(activeCampaign.id, text.platform, 0)
                                        }
                                        className="rounded-full border-white/20 bg-white/5 text-slate-100 shadow-md transition-all duration-200 hover:scale-105 hover:border-pink-400 hover:shadow-[0_0_25px_rgba(236,72,153,0.35)]"
                                      >
                                        <RefreshCw className="mr-2 h-4 w-4" />
                                        Regenerate
                                      </Button>
                                    </div>
                                  )}
                                </div>
                                {mainImage ? (
                                  <div className="relative">
                                    <img
                                      src={resolveAssetUrl(mainImage.image_url)}
                                      alt={mainImage.image_prompt || "Generated campaign visual"}
                                      className="h-full w-full rounded-md border object-cover"
                                      onError={(event) => {
                                        const target = event.target as HTMLImageElement;
                                        target.src = `${API_URL}/static/images/default_error_image.png`;
                                      }}
                                    />
                                    {mainImage.original_image_url && (
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => {
                                          // Simple comparison: open both images side by side
                                          const originalUrl = resolveAssetUrl(mainImage.original_image_url);
                                          const generatedUrl = resolveAssetUrl(mainImage.image_url);
                                          // Create a simple comparison view
                                          const comparisonWindow = window.open("", "_blank");
                                          if (comparisonWindow) {
                                            comparisonWindow.document.write(`
                                              <html>
                                                <head><title>Image Comparison</title>
                                                <style>
                                                  body { margin: 0; padding: 20px; background: #0f172a; color: white; font-family: sans-serif; }
                                                  .container { display: flex; gap: 20px; height: 90vh; }
                                                  .image-container { flex: 1; display: flex; flex-direction: column; }
                                                  .image-container h3 { margin-bottom: 10px; }
                                                  img { width: 100%; height: auto; border: 2px solid rgba(255,255,255,0.1); border-radius: 8px; }
                                                </style>
                                                </head>
                                                <body>
                                                  <h1>Image Comparison</h1>
                                                  <div class="container">
                                                    <div class="image-container">
                                                      <h3>Original</h3>
                                                      <img src="${originalUrl}" alt="Original" />
                                                    </div>
                                                    <div class="image-container">
                                                      <h3>Generated</h3>
                                                      <img src="${generatedUrl}" alt="Generated" />
                                                    </div>
                                                  </div>
                                                </body>
                                              </html>
                                            `);
                                          }
                                        }}
                                        className="absolute bottom-4 right-4 rounded-full border-white/20 bg-white/5 text-slate-100 shadow-md transition-all duration-200 hover:scale-105 hover:border-pink-400 hover:shadow-[0_0_25px_rgba(236,72,153,0.35)]"
                                        title="Compare with original"
                                      >
                                        <Eye className="mr-2 h-4 w-4" />
                                        Compare
                                      </Button>
                                    )}
                                  </div>
                                ) : (
                                  <div className="flex h-64 items-center justify-center rounded-md border border-dashed">
                                    <p className="text-sm text-slate-300">Image generation failed.</p>
                                  </div>
                                )}
                              </div>

                            <div className="flex flex-col space-y-4">
                              <div className="rounded-lg border bg-white p-4 text-gray-900 shadow-lg">
                                <div className="flex items-center justify-between">
                                  <h3 className="font-semibold text-gray-900">Caption</h3>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleCopy(text.caption)}
                                    className="rounded-full border-gray-200 bg-gray-900/5 text-gray-900 transition-all duration-200 hover:bg-gray-900 hover:text-white"
                                  >
                                    <Copy className="mr-2 h-4 w-4" />
                                    Copy
                                  </Button>
                                </div>
                                <p className="mt-3 rounded-md border border-gray-200 bg-white p-4 text-sm text-gray-900">
                                  {text.caption}
                                </p>
                              </div>

                              <div>
                                <h3 className="font-semibold text-slate-100">Analytics</h3>
                                <div className="mt-3 grid grid-cols-2 gap-4">
                                  <Card className="bg-white text-gray-900 shadow-lg">
                                    <CardHeader>
                                      <CardDescription className="text-sm font-semibold text-gray-600">Persuasiveness</CardDescription>
                                      <CardTitle
                                        className={`text-6xl font-semibold ${scoreColor(
                                          text.persuasiveness_score
                                        )}`}
                                      >
                                        {text.persuasiveness_score ?? "—"}
                                        <span className="ml-1 text-base text-gray-500">
                                          / 10
                                        </span>
                                      </CardTitle>
                                    </CardHeader>
                                  </Card>
                                  <Card className="bg-white text-gray-900 shadow-lg">
                                    <CardHeader>
                                      <CardDescription className="text-sm font-semibold text-gray-600">Clarity</CardDescription>
                                      <CardTitle
                                        className={`text-6xl font-semibold ${scoreColor(
                                          text.clarity_score
                                        )}`}
                                      >
                                        {text.clarity_score ?? "—"}
                                        <span className="ml-1 text-base text-gray-500">
                                          / 10
                                        </span>
                                      </CardTitle>
                                    </CardHeader>
                                  </Card>
                                </div>
                              </div>

                              <div>
                                <h3 className="font-semibold text-slate-100">AI feedback</h3>
                                <p className="rounded-md border bg-white p-4 text-sm italic text-gray-900">
                                  {text.feedback ? `"${text.feedback}"` : "No feedback provided."}
                                </p>
                              </div>
                            </div>
                            </div>
                          </motion.div>
                        </TabsContent>
                      );
                    })}
                  </Tabs>
                ) : (
                  <div className="flex min-h-[220px] items-center justify-center rounded-md border border-dashed">
                    <p className="text-sm text-slate-300">
                      Select a campaign from the list or generate a new one to see its outputs here.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
