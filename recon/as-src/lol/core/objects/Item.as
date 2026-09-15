class lol.core.objects.Item
{
   var __break;
   var _bg_p_cost;
   var _cost;
   var _g_cost;
   var _need_pvp_rep;
   var _weight;
   var action_map;
   var bonus_attribs;
   var bonus_ce;
   var bonus_cp;
   var bonus_hp;
   var bonus_od;
   var bonus_skills;
   var bonus_specs;
   var bonus_st;
   var desc;
   var descStrID;
   var dispatchEvent;
   var exchang;
   var name;
   var nameStrID;
   var need_attribs;
   var need_skills;
   var need_specs;
   var oID;
   var premium;
   var quest;
   var repair_mod;
   var rootID;
   var sell_mod;
   var spt;
   var spt_int;
   var tech_dif;
   var typeID;
   var uID;
   var vis;
   static var FIRE_ARM = 0;
   static var WEAR = 1;
   static var HEAL_ITEM = 2;
   static var AMMO = 3;
   static var TRASH = 4;
   static var COLD_ARM = 5;
   static var TROPHY = 6;
   static var FIST = -1;
   static var QUEST = -2;
   static var DELETE = 0;
   static var LOAD = 0;
   static var USE_IDLE = 1;
   static var USE_TARGET = 2;
   static var USE_ITEM = 3;
   static var FIRE = 4;
   static var UNLOAD = 5;
   static var USEMODE = 6;
   static var className = "Item";
   var __className = "Item";
   var inited = false;
   function Item(ID, _typeID, _rooID)
   {
      this.id = ID;
      this.typeID = _typeID;
      this.rootID = _rooID;
      lol.events.LEventDispatcher.initialize(this);
      var _loc2_;
      if(this.id != 0)
      {
         _loc2_ = lol.core.objects.ItemFactory.getProtoItem(this.typeID);
         _loc2_.addEventListener("itemUpdate",this);
         this.inited = _loc2_.inited;
      }
      this.startPC();
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("Item_" + this.id + "_" + this.typeID + "_" + this.rootID + "_" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
   function set id(oid)
   {
      this.oID = oid;
      this.uID = Number(oid.substr(0,oid.length - 6));
   }
   function get id()
   {
      return this.oID;
   }
   function initialize(obj)
   {
      this.inited = true;
      this.initGDSLStringData(obj);
      this.vis = obj.vis;
      this.weight = obj.weight;
      this.tech_dif = obj.tech_dif;
      this.exchang = obj.exchang;
      this.cost = obj.cost;
      this.bg_p_cost = obj.bg_p_cost;
      this.g_cost = obj.g_cost;
      this.repair_mod = obj.repair_mod;
      this.sell_mod = obj.sell_mod;
      this.premium = obj.premium;
      this.actions = obj.action_map;
      this.quest = obj.quest;
      this._need_pvp_rep = obj.need_pvp_rep;
   }
   function parseNeedBonus(obj)
   {
      var _loc2_;
      var _loc4_;
      var _loc5_ = obj.need_attribs_m;
      if(_loc5_)
      {
         this.need_attribs = new Array();
      }
      var _loc3_ = 0;
      _loc2_ = 0;
      while(_loc2_ < 5)
      {
         _loc4_ = _loc5_ >> _loc2_ & 1;
         if(_loc4_)
         {
            this.need_attribs[_loc2_] = obj.need_attribs[_loc3_];
            _loc3_ = _loc3_ + 1;
         }
         _loc2_ = _loc2_ + 1;
      }
      _loc5_ = obj.need_skills_m;
      if(_loc5_)
      {
         this.need_skills = new Array();
      }
      _loc3_ = 0;
      _loc2_ = 0;
      while(_loc2_ < 5)
      {
         _loc4_ = _loc5_ >> _loc2_ & 1;
         if(_loc4_)
         {
            this.need_skills[_loc2_] = obj.need_skills[_loc3_];
            _loc3_ = _loc3_ + 1;
         }
         _loc2_ = _loc2_ + 1;
      }
      _loc5_ = obj.need_specs_m;
      if(_loc5_)
      {
         this.need_specs = new Array();
      }
      _loc3_ = 0;
      _loc2_ = 0;
      while(_loc2_ < 15)
      {
         _loc4_ = _loc5_ >> _loc2_ & 1;
         if(_loc4_)
         {
            this.need_specs[_loc2_] = obj.need_specs[_loc3_];
            _loc3_ = _loc3_ + 1;
         }
         _loc2_ = _loc2_ + 1;
      }
      _loc5_ = obj.bonus_attribs_m;
      if(_loc5_)
      {
         this.bonus_attribs = new Array();
      }
      _loc3_ = 0;
      _loc2_ = 0;
      while(_loc2_ < 5)
      {
         _loc4_ = _loc5_ >> _loc2_ & 1;
         if(_loc4_)
         {
            this.bonus_attribs[_loc2_] = obj.bonus_attribs[_loc3_];
            _loc3_ = _loc3_ + 1;
         }
         _loc2_ = _loc2_ + 1;
      }
      _loc5_ = obj.bonus_skills_m;
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
            this.bonus_skills[_loc2_] = obj.bonus_skills[_loc3_];
            _loc3_ = _loc3_ + 1;
         }
         _loc2_ = _loc2_ + 1;
      }
      _loc5_ = obj.bonus_specs_m;
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
            this.bonus_specs[_loc2_] = obj.bonus_specs[_loc3_];
            _loc3_ = _loc3_ + 1;
         }
         _loc2_ = _loc2_ + 1;
      }
      this.bonus_hp = obj.bonus_hp;
      this.bonus_st = obj.bonus_st;
      this.bonus_od = obj.bonus_od;
      this.bonus_cp = obj.bonus_cp;
      this.bonus_ce = obj.bonus_ce;
   }
   function initGDSLStringData(obj)
   {
      var _loc3_ = lol.utils.StringCollector.getInstance();
      this.nameStrID = Number(obj.name);
      this.descStrID = obj.desc == "" ? null : Number(obj.desc);
      this.stringUpdate();
   }
   function stringUpdate(obj)
   {
      var _loc2_ = lol.utils.StringCollector.getInstance();
      var _loc3_ = _loc2_.getString(this.nameStrID);
      var _loc4_ = this.descStrID == null ? new lol.utils.SCString(0,"") : _loc2_.getString(this.descStrID);
      if(_loc3_ && _loc4_)
      {
         _loc2_.removeEventListener("update",this,this.stringUpdate);
         this._name = _loc3_.string;
         this.desc = _loc4_.string;
         this.dispatchEvent({type:"itemUpdate"});
      }
      else
      {
         _loc2_.addEventListener("update",this,this.stringUpdate);
      }
   }
   function _______stringUpdate(obj)
   {
      var _loc2_ = lol.utils.StringCollector.getInstance();
      var _loc3_ = _loc2_.getString(Number(this.name));
      var _loc4_ = _loc2_.getString(Number(this.desc));
      if(_loc3_ && _loc4_)
      {
         _loc2_.removeEventListener("update",this,this.stringUpdate);
         this._name = _loc3_.string;
         this.desc = _loc4_.string;
         this.dispatchEvent({type:"itemUpdate"});
      }
   }
   function set _name(value)
   {
      this.name = value;
   }
   function set need_pvp_rep(value)
   {
      this._need_pvp_rep = value;
   }
   function get need_pvp_rep()
   {
      return this._need_pvp_rep;
   }
   function updateProperties(obj)
   {
      var _loc3_ = [];
      for(var _loc4_ in obj)
      {
         if(_loc4_ == "break")
         {
            this.__break = obj[_loc4_];
         }
         else
         {
            this[_loc4_] = obj[_loc4_];
         }
         _loc3_.push(_loc4_);
      }
      this.itemUpdate(_loc3_);
   }
   function itemUpdate(param)
   {
      this.inited = true;
      this.dispatchEvent({type:"itemUpdate",p:param});
   }
   function getProp(prop)
   {
      var _loc2_;
      var _loc4_;
      if(this[prop] == undefined && this.id)
      {
         _loc4_ = lol.core.objects.ItemFactory.getProtoItem(this.typeID);
         _loc2_ = _loc4_.getProp(prop);
      }
      else
      {
         _loc2_ = this[prop];
      }
      return _loc2_;
   }
   function setProp(prop, val)
   {
      this[prop] = val;
   }
   function set actions(am)
   {
      var _loc3_ = new Array();
      _loc3_[0] = "зарядить объект";
      _loc3_[1] = "использовать объект без цели";
      _loc3_[2] = "использовать объект на некую живую цель";
      _loc3_[3] = "использовать объект на другой объект";
      _loc3_[4] = "стрельба";
      _loc3_[5] = "разрядка объекта";
      _loc3_[6] = "смена режима";
      this.action_map = new Array();
      var _loc2_ = 0;
      var _loc5_;
      var _loc4_;
      while(_loc2_ < _loc3_.length)
      {
         _loc5_ = am >> _loc2_ & 1;
         _loc4_ = 1 << _loc2_;
         this.action_map.push({type:_loc3_[_loc2_],acID:_loc4_,enable:_loc5_});
         _loc2_ = _loc2_ + 1;
      }
   }
   function get actions()
   {
      return this.getProp("action_map");
   }
   function getAP(acID)
   {
      return 0;
   }
   function set bg_p_cost(newcost)
   {
      this._bg_p_cost = newcost;
   }
   function get bg_p_cost()
   {
      return this._bg_p_cost;
   }
   function set cost(c)
   {
      this._cost = c;
   }
   function get cost()
   {
      return this._cost;
   }
   function set g_cost(c)
   {
      this._g_cost = c;
   }
   function get g_cost()
   {
      return this._g_cost;
   }
   function set weight(w)
   {
      this._weight = w;
   }
   function get weight()
   {
      return this._weight;
   }
   function get itemName()
   {
      return this.getProp("name");
   }
   function set itemName(tItemName)
   {
      this.setProp("name",tItemName);
   }
   function get itemDesc()
   {
      return this.getProp("desc");
   }
   function set itemDesc(tItemDesc)
   {
      this.setProp("desc",tItemDesc);
   }
   function get actionMap()
   {
      return this.getProp("action_map");
   }
   function set actionMap(tActionMap)
   {
      this.setProp("action_map",tActionMap);
   }
   function get visibility()
   {
      return this.getProp("vis");
   }
   function set visibility(tVisibility)
   {
      this.setProp("vis",tVisibility);
   }
   function get techDif()
   {
      return this.getProp("tech_dif");
   }
   function set techDif(tTechDif)
   {
      this.setProp("tech_dif",tTechDif);
   }
   function get exchangeable()
   {
      return this.getProp("exchang");
   }
   function set exchangeable(tExchangeable)
   {
      this.setProp("exchang",tExchangeable);
   }
   function get _break()
   {
      return this.__break;
   }
   function set _break(tBreak)
   {
      this.__break = tBreak;
   }
   function get animation_type()
   {
      return "fist";
   }
}
