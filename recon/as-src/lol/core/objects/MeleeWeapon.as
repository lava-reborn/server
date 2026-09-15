class lol.core.objects.MeleeWeapon extends lol.core.objects.Item implements lol.core.objects.Breakable
{
   var __break;
   var _animation_type;
   var _weapon_type;
   var can_aimed;
   var getProp;
   var h_damage_max;
   var h_damage_min;
   var max_break_abs;
   var max_range;
   var name;
   var parseNeedBonus;
   var setProp;
   var st_damage_max;
   var st_damage_min;
   var strike_cost;
   var strike_mod;
   var strike_time;
   var sub_name;
   static var className = "MeleeWeapon";
   var __className = "MeleeWeapon";
   static var KNIFE = 0;
   function MeleeWeapon(ID, _typeID, _rooID)
   {
      super(ID,_typeID,_rooID);
      this._animation_type = "knife";
   }
   function initialize(obj)
   {
      super.initialize(obj);
      this.h_damage_min = obj.h_damage_min;
      this.h_damage_max = obj.h_damage_max;
      this.st_damage_min = obj.st_damage_min;
      this.st_damage_max = obj.st_damage_max;
      this.max_range = obj.max_range;
      this.can_aimed = obj.can_aimed;
      this.max_break_abs = obj.max_break_abs;
      this.strike_cost = obj.strike_cost;
      this.strike_mod = obj.strike_mod;
      this.strike_time = obj.strike_time;
      this.parseNeedBonus(obj);
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
         this.sub_name = _loc4_;
      }
      this.name = value;
   }
   function getAPCost(modeNum)
   {
      var _loc2_ = this.getProp("strike_cost");
      return _loc2_[modeNum];
   }
   function getAP(acID)
   {
      var _loc2_ = this.getProp("strike_cost");
      return _loc2_;
   }
   function set weapon_type(wt)
   {
      this._weapon_type = lol.core.objects.MeleeWeapon.KNIFE;
      this._animation_type = "knife";
   }
   function get weapon_type()
   {
      return this._weapon_type;
   }
   function get animation_type()
   {
      return this._animation_type;
   }
   function getCurQuality()
   {
      var _loc3_ = this.getProp("__break");
      var _loc2_ = this.getProp("max_break_cur");
      return _loc3_ / _loc2_;
   }
   function getAbsQuality()
   {
      var _loc3_ = this.getProp("__break");
      var _loc2_ = this.getProp("max_break_abs");
      return _loc3_ / _loc2_;
   }
   function get hDamageMin()
   {
      return this.getProp("h_damage_min");
   }
   function set hDamageMin(tHDamageMin)
   {
      this.setProp("h_damage_min",tHDamageMin);
   }
   function get hDamageMax()
   {
      return this.getProp("h_damage_max");
   }
   function set hDamageMax(tHDamageMax)
   {
      this.setProp("h_damage_max",tHDamageMax);
   }
   function get stDamageMin()
   {
      return this.getProp("st_damage_min");
   }
   function set stDamageMin(tStDamageMin)
   {
      this.setProp("st_damage_min",tStDamageMin);
   }
   function get stDamageMax()
   {
      return this.getProp("st_damage_max");
   }
   function set stDamageMax(tStDamageMax)
   {
      this.setProp("st_damage_max",tStDamageMax);
   }
   function get maxRange()
   {
      return this.getProp("max_range");
   }
   function set maxRange(tMaxRange)
   {
      this.setProp("max_range",tMaxRange);
   }
   function get optRange()
   {
      return this.getProp("opt_range");
   }
   function set optRange(tOptRange)
   {
      this.setProp("opt_range",tOptRange);
   }
   function get reloadTime()
   {
      return this.getProp("reload_time");
   }
   function set reloadTime(tReloadTime)
   {
      this.setProp("reload_time",tReloadTime);
   }
   function get attackSpeed()
   {
      return this.getProp("attack_speed");
   }
   function set attackSpeed(tAttackSpeed)
   {
      this.setProp("attack_speed",tAttackSpeed);
   }
   function get canAimed()
   {
      return this.getProp("can_aimed");
   }
   function set canAimed(tCanAimed)
   {
      this.setProp("can_aimed",tCanAimed);
   }
   function get strikeCost()
   {
      return this.getProp("strike_cost");
   }
   function set strikeCost(tStrikeCost)
   {
      this.setProp("strike_cost",tStrikeCost);
   }
   function get strikeMod()
   {
      return this.getProp("strike_mod");
   }
   function set strikeMod(tStrikeMod)
   {
      this.setProp("strike_mod",tStrikeMod);
   }
   function get strikeTime()
   {
      return this.getProp("strike_time");
   }
   function set fireTime(tStrikeTime)
   {
      this.setProp("strike_time",tStrikeTime);
   }
   function get weaponType()
   {
      return this.getProp("_weapon_type");
   }
   function set weaponType(tWeaponType)
   {
      this.setProp("_weapon_type",tWeaponType);
   }
   function get needAttribs()
   {
      return this.getProp("need_attribs");
   }
   function set needAttribs(tNeedAttribs)
   {
      this.setProp("need_attribs",tNeedAttribs);
   }
   function get needSkills()
   {
      return this.getProp("need_skills");
   }
   function set needSkills(tNeedSkills)
   {
      this.setProp("need_skills",tNeedSkills);
   }
   function get needSpecs()
   {
      return this.getProp("need_specs");
   }
   function set needSpecs(tNeedSpecs)
   {
      this.setProp("need_specs",tNeedSpecs);
   }
   function get bonusAttribs()
   {
      return this.getProp("bonus_attribs");
   }
   function set bonusAttribs(tBonusAttribs)
   {
      this.setProp("bonus_attribs",tBonusAttribs);
   }
   function get bonusSkills()
   {
      return this.getProp("bonus_skills");
   }
   function set bonusSkills(tBonusSkills)
   {
      this.setProp("bonus_skills",tBonusSkills);
   }
   function get bonusSpecs()
   {
      return this.getProp("bonus_specs");
   }
   function set bonusSpecs(tBonusSpecs)
   {
      this.setProp("bonus_specs",tBonusSpecs);
   }
   function get bonusHp()
   {
      return this.getProp("bonus_hp");
   }
   function set bonusHp(tBonusHp)
   {
      this.setProp("bonus_hp",tBonusHp);
   }
   function get bonusSt()
   {
      return this.getProp("bonus_st");
   }
   function set bonusSt(tBonusSt)
   {
      this.setProp("bonus_st",tBonusSt);
   }
   function get bonusOd()
   {
      return this.getProp("bonus_od");
   }
   function set bonusOd(tBonusOd)
   {
      this.setProp("bonus_od",tBonusOd);
   }
   function get bonusCp()
   {
      return this.getProp("bonus_cp");
   }
   function set bonusCp(tBonusCp)
   {
      this.setProp("bonus_cp",tBonusCp);
   }
   function get bonusCe()
   {
      return this.getProp("bonus_ce");
   }
   function set bonusCe(tBonusCe)
   {
      this.setProp("bonus_ce",tBonusCe);
   }
   function get _break()
   {
      return this.__break;
   }
   function set _break(tBreak)
   {
      this.__break = tBreak;
   }
   function get maxBreakAbs()
   {
      return this.max_break_abs;
   }
   function set maxBreakAbs(tMaxBreakAbs)
   {
      this.max_break_abs = tMaxBreakAbs;
   }
}
