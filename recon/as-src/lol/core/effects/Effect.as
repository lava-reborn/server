class lol.core.effects.Effect
{
   var __break;
   var _armor;
   var _critical_evade;
   var _critical_probability;
   var _effect_time;
   var _em;
   var _immobilize;
   var _max_hp;
   var _max_od;
   var _max_sp;
   var _mob_drop;
   var _mob_exp;
   var _name;
   var _player_drop;
   var _player_exp;
   var _register_time;
   var _res_icon;
   var _stun;
   var _update_delta;
   var _work_time;
   var bonus_attribs;
   var bonus_skills;
   var bonus_specs;
   var id;
   var nameStrID;
   var rootID;
   var typeID;
   static var EFFECT = 0;
   var inited = false;
   function Effect(em, _ID)
   {
      lol.events.LEventDispatcher.initialize(this);
      this._em = em;
      this.typeID = _ID;
      this.id = _ID;
      this.rootID = lol.core.effects.Effect.EFFECT;
   }
   function initialize(obj, needUpdateEvent)
   {
      this.clone(obj);
      if(this._em && needUpdateEvent)
      {
         this._em.onEffectUpdate(this);
      }
   }
   function clone(obj)
   {
      this._name = obj.name;
      this._work_time = obj.work_time;
      this._update_delta = obj.update_delta;
      this.bonus_attribs = obj.bonusAttribs;
      this.bonus_skills = obj.bonusSkills;
      this.bonus_specs = obj.bonusSpecs;
      this._max_hp = obj.max_hp;
      this._max_sp = obj.max_sp;
      this._max_od = obj.max_od;
      this._critical_probability = obj.critical_probability;
      this._critical_evade = obj.critical_evade;
      this._armor = obj.armor;
      this._mob_exp = obj.mob_exp;
      if(obj.pl_exp)
      {
         this._player_exp = obj.pl_exp;
      }
      else if(obj.player_exp)
      {
         this._player_exp = obj.player_exp;
      }
      this._mob_drop = obj.mob_drop;
      if(obj.pl_drop)
      {
         this._player_drop = obj.pl_drop;
      }
      else if(obj.player_drop)
      {
         this._player_drop = obj.player_drop;
      }
      this._res_icon = obj.res_icon;
      if(obj.immob != undefined)
      {
         this._immobilize = obj.immob == 1;
      }
      else if(obj.immobilize != undefined)
      {
         this._immobilize = obj.immobilize;
      }
      if(obj.stun != undefined)
      {
         this._stun = obj.stun;
      }
      this.initGSDLStringData(obj);
      this.parseBonusArrays(obj);
      if(obj.time != undefined)
      {
         this._effect_time = obj.time;
         this._register_time = getTimer();
      }
      else if(obj.effect_time != undefined && obj.register_time != undefined)
      {
         this._effect_time = obj.effect_time;
         this._register_time = obj.register_time;
      }
      else
      {
         this._effect_time = undefined;
         this._register_time = undefined;
      }
      if(obj.inited != undefined)
      {
         this.inited = obj.inited;
      }
   }
   function get name()
   {
      return this._name;
   }
   function set name(value)
   {
      var _loc3_ = value.indexOf("$",0);
      if(_loc3_ != -1)
      {
         this._res_icon = value.substr(_loc3_ + 1,value.length);
         value = value.substr(0,_loc3_ - 1);
      }
      this._name = value;
   }
   function initGSDLStringData(obj)
   {
      this.nameStrID = Number(obj.name);
      this.stringUpdate();
   }
   function stringUpdate(obj)
   {
      var _loc2_ = lol.utils.StringCollector.getInstance();
      var _loc3_ = _loc2_.getString(this.nameStrID);
      if(_loc3_)
      {
         _loc2_.removeEventListener("update",this,this.stringUpdate);
         this.name = _loc3_.string;
         this.inited = true;
      }
      else
      {
         _loc2_.addEventListener("update",this,this.stringUpdate);
      }
   }
   function get res_icon()
   {
      return this._res_icon;
   }
   function get work_time()
   {
      return this._work_time;
   }
   function get update_delta()
   {
      return this._update_delta;
   }
   function get max_hp()
   {
      return this._max_hp;
   }
   function get max_sp()
   {
      return this._max_sp;
   }
   function get max_od()
   {
      return this._max_od;
   }
   function get critical_probability()
   {
      return this._critical_probability;
   }
   function get critical_evade()
   {
      return this._critical_evade;
   }
   function get armor()
   {
      return this._armor;
   }
   function get mob_exp()
   {
      return this._mob_exp;
   }
   function get player_exp()
   {
      return this._player_exp;
   }
   function get mob_drop()
   {
      return this._mob_drop;
   }
   function get player_drop()
   {
      return this._player_drop;
   }
   function get immobilize()
   {
      return this._immobilize;
   }
   function get stun()
   {
      return this._stun;
   }
   function get bonusAttribs()
   {
      return this.bonus_attribs;
   }
   function set bonusAttribs(tBonusAttribs)
   {
      this.setProp("bonus_attribs",tBonusAttribs);
   }
   function get bonusSkills()
   {
      return this.bonus_skills;
   }
   function set bonusSkills(tBonusSkills)
   {
      this.setProp("bonus_skills",tBonusSkills);
   }
   function get bonusSpecs()
   {
      return this.bonus_specs;
   }
   function set bonusSpecs(tBonusSpecs)
   {
      this.setProp("bonus_specs",tBonusSpecs);
   }
   function toString()
   {
      var _loc2_;
      _loc2_ = "EFFECTS.Effect.toString = ";
      for(var _loc3_ in this)
      {
         _loc2_ += _loc3_ + " = " + this[_loc3_] + "| ";
      }
      return _loc2_;
   }
   function setProp(prop, val)
   {
      this[prop] = val;
   }
   function get effect_time()
   {
      return this._effect_time;
   }
   function set effect_time(ET)
   {
      this._effect_time = ET;
      this._register_time = getTimer();
   }
   function get register_time()
   {
      return this._register_time;
   }
   function parseBonusArrays(obj)
   {
      var _loc2_;
      var _loc4_;
      var _loc5_ = obj.attribs_mask;
      if(_loc5_)
      {
         this.bonus_attribs = new Array();
      }
      var _loc3_ = 0;
      _loc2_ = 0;
      while(_loc2_ < 5)
      {
         _loc4_ = _loc5_ >> _loc2_ & 1;
         if(_loc4_)
         {
            this.bonus_attribs[_loc2_] = obj.attribs[_loc3_];
            _loc3_ = _loc3_ + 1;
         }
         _loc2_ = _loc2_ + 1;
      }
      _loc5_ = obj.skills_mask;
      if(_loc5_)
      {
         this.bonus_skills = new Array();
      }
      _loc3_ = 0;
      _loc2_ = 0;
      while(_loc2_ < 5)
      {
         _loc4_ = _loc5_ >> _loc2_ & 1;
         if(_loc4_)
         {
            this.bonus_skills[_loc2_] = obj.skills[_loc3_];
            _loc3_ = _loc3_ + 1;
         }
         _loc2_ = _loc2_ + 1;
      }
      _loc5_ = obj.specs_mask;
      if(_loc5_)
      {
         this.bonus_specs = new Array();
      }
      _loc3_ = 0;
      _loc2_ = 0;
      while(_loc2_ < 15)
      {
         _loc4_ = _loc5_ >> _loc2_ & 1;
         if(_loc4_)
         {
            this.bonus_specs[_loc2_] = obj.specs[_loc3_];
            _loc3_ = _loc3_ + 1;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function updateProperties(obj, needUpdateEvent)
   {
      for(var _loc3_ in obj)
      {
         if(_loc3_ == "break")
         {
            this.__break = obj[_loc3_];
         }
         else if(_loc3_ == "time")
         {
            this.effect_time = obj[_loc3_];
         }
         else
         {
            this[_loc3_] = obj[_loc3_];
         }
      }
      if(this._em && needUpdateEvent)
      {
         this._em.onEffectUpdate(this);
      }
   }
   function isBuff()
   {
      var _loc2_;
      _loc2_ = 0;
      while(_loc2_ < this.bonus_attribs.length)
      {
         if(this.bonus_attribs[_loc2_] < 0)
         {
            return false;
         }
         _loc2_ = _loc2_ + 1;
      }
      _loc2_ = 0;
      while(_loc2_ < this.bonus_skills.length)
      {
         if(this.bonus_skills[_loc2_] < 0)
         {
            return false;
         }
         _loc2_ = _loc2_ + 1;
      }
      _loc2_ = 0;
      while(_loc2_ < this.bonus_specs.length)
      {
         if(this.bonus_specs[_loc2_] < 0)
         {
            return false;
         }
         _loc2_ = _loc2_ + 1;
      }
      if(this._max_hp < 0)
      {
         return false;
      }
      if(this._max_sp < 0)
      {
         return false;
      }
      if(this._max_od < 0)
      {
         return false;
      }
      if(this._critical_probability < 0)
      {
         return false;
      }
      if(this._critical_evade < 0)
      {
         return false;
      }
      if(this._armor < 0)
      {
         return false;
      }
      if(this._mob_exp < 1)
      {
         return false;
      }
      if(this._player_exp < 1)
      {
         return false;
      }
      if(this._mob_drop < 1)
      {
         return false;
      }
      if(this._player_drop < 1)
      {
         return false;
      }
      if(this._immobilize)
      {
         return false;
      }
      if(this._stun)
      {
         return false;
      }
      return true;
   }
   function getDebuffString()
   {
      if(this._max_hp < 0)
      {
         return "Я хирею!..";
      }
      if(this._max_sp < 0)
      {
         return "Я слабее!";
      }
      if(this._max_od < 0)
      {
         return "Надо передохнуть";
      }
      if(this._critical_probability < 0)
      {
         return "Мои криты ни к черту!";
      }
      if(this._critical_evade < 0)
      {
         return "Сложнее уворачиваться!";
      }
      if(this._armor)
      {
         return "Моя броня!..";
      }
      if(this._mob_exp < 1)
      {
         return "Стало меньше опыта!";
      }
      if(this._immobilize)
      {
         return "Моя нога-а!";
      }
      if(this._stun)
      {
         return "Меня парализова...";
      }
   }
}
