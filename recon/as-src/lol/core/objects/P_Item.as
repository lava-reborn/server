class lol.core.objects.P_Item extends Object
{
   var _item;
   var dispatchEvent;
   var spt;
   var spt_int;
   function P_Item()
   {
      super();
      lol.events.LEventDispatcher.initialize(this);
      this.startPC();
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("P_Item_" + this.id + "_" + this.typeID + "_" + this.rootID + "_" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
   function initialize(obj)
   {
      this.item.initialize(obj);
   }
   function set item(__item)
   {
      this._item = __item;
      this._item.addEventListener("itemUpdate",this,this.dispatchItemUpdate);
   }
   function get item()
   {
      return this._item;
   }
   function dispatchItemUpdate(obj)
   {
      this.dispatchEvent({type:"itemUpdate"});
   }
   function getProp(prop)
   {
      return this.item.getProp(prop);
   }
   function setProp(prop, val)
   {
      this.item.setProp(prop,val);
   }
   function get id()
   {
      return this.item.id;
   }
   function get typeID()
   {
      return this.item.typeID;
   }
   function get rootID()
   {
      return this.item.rootID;
   }
   function get inited()
   {
      return this.item.inited;
   }
}
