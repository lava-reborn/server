class lol.core.GConstatns
{
   var XMC;
   var gold_to_afro_rate;
   var leave_combat_timeout;
   var max_number_of_quests;
   static var _ref;
   static var daily_max;
   static var daily_reset_time;
   static var gold_repair_mod;
   static var gold_restore_price_mod;
   static var premium_break_bonus_1;
   static var premium_break_bonus_2;
   static var premium_weight_bonus_1;
   static var premium_weight_bonus_2;
   static var premium_xp_bonus_1;
   static var premium_xp_bonus_2;
   function GConstatns()
   {
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("constants",this);
   }
   function constants(obj)
   {
      this.gold_to_afro_rate = obj.param.gold_to_afro_rate;
      this.max_number_of_quests = obj.param.quest_log_capacity;
      this.leave_combat_timeout = obj.param.leave_combat_timeout;
      lol.core.GConstatns.premium_weight_bonus_1 = obj.param.premium_weight_bonus_1;
      lol.core.GConstatns.premium_weight_bonus_2 = obj.param.premium_weight_bonus_2;
      lol.core.GConstatns.premium_break_bonus_1 = obj.param.premium_break_bonus_1;
      lol.core.GConstatns.premium_break_bonus_2 = obj.param.premium_break_bonus_2;
      lol.core.GConstatns.premium_xp_bonus_1 = obj.param.premium_xp_bonus_1;
      lol.core.GConstatns.premium_xp_bonus_2 = obj.param.premium_xp_bonus_2;
      lol.core.GConstatns.gold_restore_price_mod = obj.param.gold_repair_price_mod;
      if(obj.param.gold_repair_mod)
      {
         lol.core.GConstatns.gold_repair_mod = obj.param.gold_repair_mod;
      }
      else
      {
         lol.core.GConstatns.gold_repair_mod = 10000;
      }
      lol.core.GConstatns.daily_max = obj.param.daily_max;
      lol.core.GConstatns.daily_reset_time = obj.param.daily_reset_time;
   }
   static function getGoldToAfroRate()
   {
      return lol.core.GConstatns._ref.gold_to_afro_rate;
   }
   static function getMaxNumberOfQuests()
   {
      return lol.core.GConstatns._ref.max_number_of_quests;
   }
   static function getLeaveCombatLocationPause()
   {
      return lol.core.GConstatns._ref.leave_combat_timeout;
   }
   static function create()
   {
      lol.core.GConstatns._ref = new lol.core.GConstatns();
   }
}
