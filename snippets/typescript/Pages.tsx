import * as React from "react";
import { Routes, Route } from "react-router-dom";
import Meal from "./diet/Dishes";
import Dish from "./diet/Dish";
import Diet from "./diet/Diet";
import BudgetsPage from "./finance/BudgetsPage";
import VoiceEmailReader from "./inbox/VoiceEmailReader";
import InvestmentPlannerPage from "./finance/InvestmentPlannerPage";
import ReceiptSplitManager from "./shopping/ReceiptSplitManager";
import BodyFatPlanner from "./diet/BodyFatPlanner";
import ShoppingListManager from "./shopping/ShoppingListManager";
import SharedShoppingListPage from "./shopping/SharedShoppingList";

type PageMetaData = {
  name: string;
  link: string;
  pageComponent: React.ReactNode;
  shareComponent?: React.ReactNode;
};

export type ValidViews = "diet" | "finance" | "shopping" | "inbox";
export const validViewsValues = ["diet", "finance", "shopping", "inbox"];

export type Pages = {
  [K in ValidViews]: PageMetaData[];
};

/**
 * a list containing the metadata of the pages, including { name, pageIcon and link, pageComponent }
 */
export const pages: Pages = {
  finance: [
    {
      name: "Plan Investments",
      link: "/investments",
      pageComponent: <InvestmentPlannerPage />,
    },
    {
      name: "Plan Finances",
      link: "/finance",
      pageComponent: <BudgetsPage />,
    },
  ],
  diet: [
    {
      name: "Body Fat Planner",
      link: "/body-fat-planner",
      pageComponent: <BodyFatPlanner />,
    },
    {
      name: "Plan Diet",
      link: "/diet",
      pageComponent: <Diet />,
    },
    {
      name: "Edit Dishes",
      link: "/dishes",
      pageComponent: <Meal />,
    },
    {
      name: "Add Dish",
      link: "/dish",
      pageComponent: <Dish />,
    },
  ],
  shopping: [
    {
      name: "Shopping Lists",
      link: "/shopping",
      pageComponent: <ShoppingListManager />,
      shareComponent: <SharedShoppingListPage />,
    },
    {
      name: "Receipt Split",
      link: "/receipts",
      pageComponent: <ReceiptSplitManager />,
    },
  ],
  inbox: [
    {
      name: "Voice Reader",
      link: "/inbox",
      pageComponent: <VoiceEmailReader />,
    },
  ],
};

export default function Pages() {
  return (
    <Routes>
      <Route path="/" element={<ShoppingListManager />} />
      {Object.values(pages)
        .flat()
        .map((pageMetaData, index) => {
          return (
            <React.Fragment key={index}>
              <Route path={pageMetaData.link} element={pageMetaData.pageComponent} />
              {pageMetaData.shareComponent && (
                <Route
                  key={`${index}-share`}
                  path={`${pageMetaData.link}/share/:identifier`}
                  element={pageMetaData.shareComponent}
                />
              )}
            </React.Fragment>
          );
        })}
    </Routes>
  );
}
