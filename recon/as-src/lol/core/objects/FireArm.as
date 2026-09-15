class lol.core.objects.FireArm extends lol.core.objects.Item implements lol.core.objects.Breakable
{
   var __break;
   var __lastAmmo;
   var __lastAmmoType;
   var _animation_type;
   var _weapon_type;
   var accuracy;
   var ammo_count;
   var ammo_type;
   var clip_size;
   var comp_ammo;
   var cur_mode;
   var end_opt_range;
   var fire_costs;
   var fire_mods;
   var fire_times;
   var getProp;
   var h_damage_max;
   var h_damage_min;
   var max_break_abs;
   var max_break_cur;
   var max_range;
   var name;
   var opt_range;
   var parseNeedBonus;
   var piercing;
   var rating;
   var reload_cost;
   var reload_time;
   var setProp;
   var st_damage_max;
   var st_damage_min;
   var sub_name;
   var target_size;
   static var className = "FireArm";
   var __className = "FireArm";
   static var PISTOL = 0;
   static var SHOTGUN = 1;
   static var ASSAULT = 2;
   static var RIFLE = 3;
   static var MACHINEGUN = 4;
   static var SMG = 5;
   var _ammo = 0;
   var __maxAmmo = 30;
   function FireArm(ID, _typeID, _rooID)
   {
      super(ID,_typeID,_rooID);
      lol.core.Master.getInstance().gamer.equipment.getAmmo(this);
   }
   function initialize(obj)
   {
      super.initialize(obj);
      this.h_damage_min = obj.h_damage_min;
      this.h_damage_max = obj.h_damage_max;
      this.st_damage_min = obj.st_damage_min;
      this.st_damage_max = obj.st_damage_max;
      this.max_range = obj.max_range;
      this.opt_range = obj.opt_range;
      this.end_opt_range = obj.end_opt_range;
      this.reload_time = obj.reload_time;
      this.reload_cost = obj.reload_cost;
      this.target_size = obj.target_size;
      this.max_break_abs = obj.max_break_abs;
      this.clip_size = obj.clip_size;
      this.comp_ammo = obj.comp_array;
      this.fire_costs = obj.fire_costs;
      this.fire_mods = obj.fire_mods;
      this.fire_times = obj.fire_times;
      this.piercing = obj.piercing;
      this.ammo_count = obj.ammo_count;
      this.weapon_type = obj.weapon_type;
      this.parseNeedBonus(obj);
      this.countRating();
      this.countAccuracy();
   }
   function countAccuracy()
   {
      this.accuracy = new Array();
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < 3)
      {
         _loc3_ = Math.round(1000 * this.target_size[_loc2_] / this.max_range[_loc2_]) / 10;
         this.accuracy.push(_loc3_);
         _loc2_ = _loc2_ + 1;
      }
   }
   function countRating()
   {
      var _loc6_ = new Array();
      var _loc2_ = 0;
      var _loc4_;
      var _loc3_;
      var _loc5_;
      while(_loc2_ < 3)
      {
         if(this.fire_mods[_loc2_])
         {
            _loc4_ = ((this.h_damage_min[_loc2_] + this.h_damage_max[_loc2_]) / 2 + (this.h_damage_max[_loc2_] - this.h_damage_min[_loc2_]) / 4) / this.fire_costs[_loc2_] * this.fire_mods[_loc2_] * 10;
            _loc3_ = 100 * this.target_size[_loc2_] / this.max_range[_loc2_] / 5;
            _loc5_ = _loc4_ - this.fire_times[_loc2_] / 1000 - _loc3_ + this.end_opt_range[_loc2_] - this.opt_range[_loc2_] + this.max_range[_loc2_] / 10 - this.reload_time / 1000 - this.reload_cost / 10 + this.clip_size / 10;
            _loc6_[_loc2_] = _loc5_;
         }
         _loc2_ = _loc2_ + 1;
      }
      this.rating = Math.round(this.getMax(_loc6_[0],_loc6_[1],_loc6_[2]));
   }
   function getMax(value0, value1, value2)
   {
      var _loc2_ = 0;
      if(value0 > _loc2_ && this.fire_mods[0])
      {
         _loc2_ = value0;
      }
      if(value1 > _loc2_ && this.fire_mods[1])
      {
         _loc2_ = value1;
      }
      if(value2 > _loc2_ && this.fire_mods[2])
      {
         _loc2_ = value2;
      }
      return _loc2_;
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
   function compare(ammo)
   {
      var _loc3_ = this.getProp("comp_ammo");
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_] == ammo.typeID)
         {
            return true;
         }
         _loc2_ = _loc2_ + 1;
      }
      return false;
   }
   function get lastAmmo()
   {
      return this.__lastAmmo;
   }
   function set lastAmmo(ammo)
   {
      this.__lastAmmo = ammo;
      this.__lastAmmoType = ammo.typeID;
   }
   function loadAmmo(q)
   {
      this._ammo += q;
      var _loc2_ = 0;
      if(this._ammo > this.__maxAmmo)
      {
         this._ammo = this.__maxAmmo;
      }
   }
   function unloadAmmo()
   {
      var _loc2_ = this._ammo;
      this._ammo = 0;
      return _loc2_;
   }
   function getAPCost(modeNum)
   {
      var _loc2_ = this.getProp("fire_costs");
      return _loc2_[modeNum];
   }
   function getAP(acID)
   {
      var _loc3_;
      if(acID == lol.core.objects.Item.FIRE || acID == undefined)
      {
         _loc3_ = this.getProp("fire_costs");
         return _loc3_[this.cur_mode];
      }
      if(acID == lol.core.objects.Item.USEMODE)
      {
         return 0;
      }
      if(acID == lol.core.objects.Item.LOAD || acID == lol.core.objects.Item.UNLOAD)
      {
         return this.reloadCost;
      }
      return 10;
   }
   function set weapon_type(wt)
   {
      this._weapon_type = wt;
      switch(wt)
      {
         case 0:
            this._animation_type = "pistol";
            break;
         case 1:
            this._animation_type = "rifle";
            break;
         case 2:
            this._animation_type = "rifle";
            break;
         case 3:
            this._animation_type = "rifle";
            break;
         case 4:
            this._animation_type = "rifle";
            break;
         case 5:
            this._animation_type = "rifle";
            break;
         default:
            this._animation_type = "rifle";
      }
   }
   function get weapon_type()
   {
      return this._weapon_type;
   }
   function get animation_type()
   {
      return this.getProp("_animation_type");
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
   function get reloadCost()
   {
      return this.getProp("reload_cost");
   }
   function set attackSpeed(tAttackSpeed)
   {
      this.setProp("attack_speed",tAttackSpeed);
   }
   function get canAimedSh()
   {
      return this.getProp("can_aimed_sh");
   }
   function set canAimedSh(tCanAimedSh)
   {
      this.setProp("can_aimed_sh",tCanAimedSh);
   }
   function get fireCosts()
   {
      return this.getProp("fire_costs");
   }
   function set fireCosts(tFireCosts)
   {
      this.setProp("fire_costs",tFireCosts);
   }
   function get fireMods()
   {
      return this.getProp("fire_mods");
   }
   function set fireMods(tFireMods)
   {
      this.setProp("fire_mods",tFireMods);
   }
   function get fireTimes()
   {
      return this.getProp("fire_times");
   }
   function set fireTimes(tFireTimes)
   {
      this.setProp("fire_times",tFireTimes);
   }
   function get clipSize()
   {
      return this.getProp("clip_size");
   }
   function set clipSize(tClipSize)
   {
      this.setProp("clip_size",tClipSize);
   }
   function get compAmmo()
   {
      return this.getProp("comp_ammo");
   }
   function set compAmmo(tCompAmmo)
   {
      this.setProp("comp_ammo",tCompAmmo);
   }
   function get curMode()
   {
      return this.getProp("cur_mode");
   }
   function set curMode(tCurMode)
   {
      this.setProp("cur_mode",tCurMode);
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
   function get maxBreakCur()
   {
      return this.max_break_cur;
   }
   function set maxBreakCur(tMaxBreakCur)
   {
      this.max_break_cur = tMaxBreakCur;
   }
   function get maxBreakAbs()
   {
      return this.max_break_abs;
   }
   function set maxBreakAbs(tMaxBreakAbs)
   {
      this.max_break_abs = tMaxBreakAbs;
   }
   function get ammoType()
   {
      if(this.ammoCount == 0)
      {
         return undefined;
      }
      return this.ammo_type;
   }
   function set ammoType(tAmmoType)
   {
      this.ammo_type = tAmmoType;
   }
   function get ammoCount()
   {
      return this.ammo_count;
   }
   function set ammoCount(tAmmoCount)
   {
      this.ammo_count = tAmmoCount;
   }
}
