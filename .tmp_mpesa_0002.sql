--
-- Add field order to payment
--
ALTER TABLE `payments` ADD COLUMN `order_id` bigint NOT NULL , ADD CONSTRAINT `payments_order_id_6086ad70_fk_orders_order_id` FOREIGN KEY (`order_id`) REFERENCES `orders_order`(`id`);
CREATE INDEX `payments_order_id_6086ad70` ON `payments` (`order_id`);
