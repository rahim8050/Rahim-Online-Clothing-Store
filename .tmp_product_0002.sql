--
-- Create model ListingCheckout
--
CREATE TABLE `product_app_listingcheckout` (`id` bigint AUTO_INCREMENT NOT NULL PRIMARY KEY, `product_version` integer UNSIGNED NOT NULL CHECK (`product_version` >= 0), `amount` numeric(10, 2) NOT NULL, `currency` varchar(3) NOT NULL, `status` varchar(16) NOT NULL, `gateway` varchar(50) NOT NULL, `provider_ref` varchar(100) NOT NULL UNIQUE, `created_at` datetime(6) NOT NULL);
--
-- Add field owner to product
--
ALTER TABLE `product_app_product` ADD COLUMN `owner_id` bigint DEFAULT 1 NOT NULL , ADD CONSTRAINT `product_app_product_owner_id_964353f3_fk_users_customuser_id` FOREIGN KEY (`owner_id`) REFERENCES `users_customuser`(`id`);
ALTER TABLE `product_app_product` ALTER COLUMN `owner_id` DROP DEFAULT;
--
-- Add field published_version to product
--
ALTER TABLE `product_app_product` ADD COLUMN `published_version` integer UNSIGNED NULL CHECK (`published_version` >= 0);
--
-- Add field status to product
--
ALTER TABLE `product_app_product` ADD COLUMN `status` varchar(32) DEFAULT 'DRAFT' NOT NULL;
ALTER TABLE `product_app_product` ALTER COLUMN `status` DROP DEFAULT;
--
-- Add field version to product
--
ALTER TABLE `product_app_product` ADD COLUMN `version` integer UNSIGNED DEFAULT 1 NOT NULL CHECK (`version` >= 0);
ALTER TABLE `product_app_product` ALTER COLUMN `version` DROP DEFAULT;
--
-- Create constraint product_price_gte_0 on model product
--
ALTER TABLE `product_app_product` ADD CONSTRAINT `product_price_gte_0` CHECK (`price` >= 0);
--
-- Add field created_by to listingcheckout
--
ALTER TABLE `product_app_listingcheckout` ADD COLUMN `created_by_id` bigint NOT NULL , ADD CONSTRAINT `product_app_listingc_created_by_id_e8bd58a4_fk_users_cus` FOREIGN KEY (`created_by_id`) REFERENCES `users_customuser`(`id`);
--
-- Add field product to listingcheckout
--
ALTER TABLE `product_app_listingcheckout` ADD COLUMN `product_id` bigint NOT NULL , ADD CONSTRAINT `product_app_listingc_product_id_1c60a24c_fk_product_a` FOREIGN KEY (`product_id`) REFERENCES `product_app_product`(`id`);
CREATE INDEX `product_app_product_owner_id_964353f3` ON `product_app_product` (`owner_id`);
CREATE INDEX `product_app_listingcheckout_created_by_id_e8bd58a4` ON `product_app_listingcheckout` (`created_by_id`);
CREATE INDEX `product_app_listingcheckout_product_id_1c60a24c` ON `product_app_listingcheckout` (`product_id`);
