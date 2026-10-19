import { notFound } from "next/navigation";

import { PeopleDirectory } from "@/components/people/people-directory";

const categories = ["lawyers", "witnesses", "beneficiaries"] as const;
type PeopleCategory = (typeof categories)[number];

export default async function PeopleCategoryPage({ params }: { params: Promise<{ category: string }> }) {
  const { category } = await params;
  if (!categories.includes(category as PeopleCategory)) notFound();
  return <PeopleDirectory category={category as PeopleCategory} />;
}