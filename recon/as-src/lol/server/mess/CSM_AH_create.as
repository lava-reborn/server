class lol.server.mess.CSM_AH_create extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_AH_create(target, obj, time, a_bid, a_buyout, g_bid, g_buyout)
   {
      super();
      this._name = "ah_create";
      this.addProp("g_buyout",g_buyout);
      this.addProp("g_bid",g_bid);
      this.addProp("a_buyout",a_buyout);
      this.addProp("a_bid",a_bid);
      this.addProp("time",time);
      this.addProp("obj",obj);
      this.addProp("target",target);
   }
}
