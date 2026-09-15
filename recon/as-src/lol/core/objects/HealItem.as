class lol.core.objects.HealItem extends lol.core.objects.Item
{
   var _effects;
   var bonus_act_time;
   var bonus_prob;
   var can_rest_br;
   var dex_bonus;
   var effects_prob;
   var getProp;
   var heal_cost;
   var heal_time;
   var int_bonus;
   var max_h_rest;
   var max_st_rest;
   var max_use_count;
   var min_h_rest;
   var min_st_rest;
   var name;
   var parseNeedBonus;
   var per_bonus;
   var processed_effects;
   var setProp;
   var sta_bonus;
   var str_bonus;
   var use_count;
   static var className = "HealItem";
   var __className = "HealItem";
   function HealItem(ID, _typeID, _rooID)
   {
      super(ID,_typeID,_rooID);
      lol.core.Master.getInstance().gamer.equipment.getEffects(this);
   }
   function initialize(obj)
   {
      this.heal_time = obj.heal_time;
      this.max_h_rest = obj.max_h_rest;
      this.max_st_rest = obj.max_st_rest;
      this.min_h_rest = obj.min_h_rest;
      this.min_st_rest = obj.min_st_rest;
      this.max_use_count = obj.use_count;
      this.bonus_prob = obj.bonus_prob;
      this.bonus_act_time = obj.bonus_act_time;
      this.can_rest_br = obj.can_rest_br;
      this.str_bonus = obj.str_bonus;
      this.dex_bonus = obj.dex_bonus;
      this.sta_bonus = obj.sta_bonus;
      this.per_bonus = obj.per_bonus;
      this.int_bonus = obj.int_bonus;
      this.heal_cost = obj.heal_cost;
      this._effects = obj.effects;
      this.effects_prob = obj.effects_prob;
      super.initialize(obj);
      this.parseNeedBonus(obj);
      this.processed_effects = lol.core.Master.getInstance().gamer.equipment.getEffects(this);
   }
   function set _name(value)
   {
      var _loc3_ = value.indexOf("$",0);
      var _loc4_;
      if(_loc3_ != -1)
      {
         _loc4_ = value.substr(_loc3_ + 1,value.length);
         this.setProp("sub_name",_loc4_);
         value = value.substr(0,_loc3_);
      }
      this.name = value;
   }
   function getAP()
   {
      return this.heal_cost;
   }
   function get effects()
   {
      var _loc2_ = this.getProp("_effects");
      return _loc2_;
   }
   function set effects(tEffects)
   {
      this.setProp("_effects",tEffects);
   }
   function get healTime()
   {
      return this.getProp("heal_time");
   }
   function set healTime(tHealTime)
   {
      this.setProp("heal_time",tHealTime);
   }
   function get maxHealthRestore()
   {
      return this.getProp("max_h_rest");
   }
   function set maxHealthRestore(tMaxHealthRestore)
   {
      this.setProp("max_h_rest",tMaxHealthRestore);
   }
   function get maxStaminaRestore()
   {
      return this.getProp("max_st_rest");
   }
   function set maxStaminaRestore(tMaxStaminaRestore)
   {
      this.setProp("max_st_rest",tMaxStaminaRestore);
   }
   function get minHealthRestore()
   {
      return this.getProp("min_h_rest");
   }
   function set minHealthRestore(tMinHealthRestore)
   {
      this.setProp("min_h_rest",tMinHealthRestore);
   }
   function get minStaminaRestore()
   {
      return this.getProp("min_st_rest");
   }
   function set minStaminaRestore(tMinStaminaRestore)
   {
      this.setProp("min_st_rest",tMinStaminaRestore);
   }
   function get bonusProbability()
   {
      return this.getProp("bonus_prob");
   }
   function set bonusProbability(tBonusProbability)
   {
      this.setProp("bonus_prob",tBonusProbability);
   }
   function get bonusActiveTime()
   {
      return this.getProp("bonus_act_time");
   }
   function set bonusActiveTime(tBonusActiveTime)
   {
      this.setProp("bonus_act_time",tBonusActiveTime);
   }
   function get canRestoreBreaks()
   {
      return this.getProp("can_rest_br");
   }
   function set canRestoreBreaks(tCanRestoreBreaks)
   {
      this.setProp("can_rest_br",tCanRestoreBreaks);
   }
   function get strBonus()
   {
      return this.getProp("str_bonus");
   }
   function set strBonus(tStrBonus)
   {
      this.setProp("str_bonus",tStrBonus);
   }
   function get dexBonus()
   {
      return this.getProp("dex_bonus");
   }
   function set dexBonus(tDexBonus)
   {
      this.setProp("dex_bonus",tDexBonus);
   }
   function get staBonus()
   {
      return this.getProp("sta_bonus");
   }
   function set staBonus(tStaBonus)
   {
      this.setProp("sta_bonus",tStaBonus);
   }
   function get perBonus()
   {
      return this.getProp("per_bonus");
   }
   function set perBonus(tPerBonus)
   {
      this.setProp("per_bonus",tPerBonus);
   }
   function get intBonus()
   {
      return this.getProp("int_bonus");
   }
   function set intBonus(tIntBonus)
   {
      this.setProp("int_bonus",tIntBonus);
   }
   function get maxUseCount()
   {
      return this.getProp("max_use_count");
   }
   function set maxUseCount(tMaxUseCount)
   {
      this.setProp("max_use_count",tMaxUseCount);
   }
   function get isHeal()
   {
      if(this.getProp("max_h_rest") == undefined || this.getProp("max_st_rest") == undefined)
      {
         return undefined;
      }
      if(this.getProp("max_h_rest") >= this.getProp("max_st_rest"))
      {
         return true;
      }
      return false;
   }
   function get isBuff()
   {
      var _loc2_ = this.getProp("_effects");
      if(_loc2_ != undefined)
      {
         return _loc2_.length > 0;
      }
   }
   function get useCount()
   {
      return this.use_count;
   }
   function set useCount(tUseCount)
   {
      this.use_count = tUseCount;
   }
}
